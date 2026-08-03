import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(TOOLS_DIR))
HERO_SELECT_FIXTURES_DIR = FIXTURES_DIR / "hauntedroom-captures" / "hero_select"

from hauntedroom.flows.automap import (
    AUTOMAP_POLL_MS,
    LV_SPIN_CLICK_OFFSET_X,
    UPGRADE_CONFIRM_CLICK,
    run_automap_flow,
)
from hauntedroom.flows.automap_support.detectors import (
    PROTECT_AVAILABLE_REGION,
    region_has_enough_white,
)


class LevelUpTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.mouse.move = AsyncMock()
        self.page.mouse.down = AsyncMock()
        self.page.mouse.up = AsyncMock()

    @staticmethod
    def make_protect_available(image):
        x1, y1, _, _ = PROTECT_AVAILABLE_REGION
        image[y1 : y1 + 2, x1 : x1 + 4] = (255, 255, 255)
        return image

    def test_region_requires_enough_white_inside_configured_rectangle(self):
        image = np.zeros((720, 640, 3), dtype=np.uint8)
        x1, y1, _, _ = PROTECT_AVAILABLE_REGION
        image[y1 : y1 + 2, x1 : x1 + 3] = (255, 255, 255)
        self.assertFalse(region_has_enough_white(image))

        image[y1 : y1 + 2, x1 : x1 + 4] = (255, 255, 255)
        self.assertTrue(region_has_enough_white(image))

    def test_region_does_not_treat_gold_as_white(self):
        image = np.zeros((720, 640, 3), dtype=np.uint8)
        x1, y1, x2, y2 = PROTECT_AVAILABLE_REGION
        image[y1:y2, x1:x2] = (40, 180, 245)

        self.assertFalse(region_has_enough_white(image))

    def test_region_outside_image_fails_closed(self):
        image = np.full((100, 100, 3), 255, dtype=np.uint8)

        self.assertFalse(region_has_enough_white(image))

    def test_available_and_unavailable_reference_colors(self):
        misc_dir = TOOLS_DIR / "rooms" / "misc"
        available = cv2.imread(str(misc_dir / "white_available.png"))
        unavailable = cv2.imread(str(misc_dir / "red_unavailable.png"))

        self.assertTrue(
            region_has_enough_white(available, region=(90, 8, 140, 30))
        )
        self.assertFalse(
            region_has_enough_white(unavailable, region=(90, 8, 140, 30))
        )

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template", return_value=(200, 20, 0.92))
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_level_spin_interrupt_clicks_left_offset_before_protect_gate(
        self,
        capture_page_bgr,
        find_template_matches,
        _find_template,
        _load_template,
    ):
        capture_page_bgr.return_value = self.make_protect_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )
        find_template_matches.return_value = []
        stop_event = asyncio.Event()

        async def stop_after_first_click(*_args, **_kwargs):
            stop_event.set()

        self.page.mouse.click.side_effect = stop_after_first_click

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.page.mouse.click.assert_awaited_once_with(
            max(0, 200 + LV_SPIN_CLICK_OFFSET_X),
            560,
        )
        self.page.wait_for_timeout.assert_awaited_once_with(AUTOMAP_POLL_MS)

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.automap.find_template",
        side_effect=[(0, 0, 0.0), (0, 0, 0.0), (200, 20, 0.92)],
    )
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_level_up_rechecks_level_spin_before_confirm_click(
        self,
        capture_page_bgr,
        find_template_matches,
        _find_template,
        _load_template,
    ):
        capture_page_bgr.side_effect = [
            np.zeros((720, 640, 3), dtype=np.uint8),
            np.zeros((720, 640, 3), dtype=np.uint8),
        ]
        find_template_matches.side_effect = [
            [(120, 500, 0.91)],
        ]
        stop_event = asyncio.Event()

        async def stop_after_level_spin_click(*_args, **_kwargs):
            if self.page.mouse.click.await_count == 2:
                stop_event.set()

        self.page.mouse.click.side_effect = stop_after_level_spin_click

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(120, 500),
                call(max(0, 200 + LV_SPIN_CLICK_OFFSET_X), 560),
            ],
        )

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template", return_value=(0, 0, 0.0))
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_level_up_uses_largest_y_and_rechecks_before_confirm(
        self,
        capture_page_bgr,
        find_template_matches,
        _find_template,
        _load_template,
    ):
        unavailable = np.zeros((720, 640, 3), dtype=np.uint8)
        available = cv2.imread(
            str(
                HERO_SELECT_FIXTURES_DIR
                / "3_option_hanu_xlubu.png"
            )
        )
        capture_page_bgr.side_effect = [
            unavailable,
            unavailable,
            available,
        ]
        find_template_matches.side_effect = [
            [
                (100, 200, 0.99),
                (120, 500, 0.91),
            ],
            [],
            [],
        ]
        stop_event = asyncio.Event()

        async def stop_after_hero_levelup_select(*_args, **_kwargs):
            if self.page.mouse.click.await_count == 3:
                stop_event.set()

        self.page.mouse.click.side_effect = stop_after_hero_levelup_select

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(120, 500),
                call(*UPGRADE_CONFIRM_CLICK),
                call(347, 597),
            ],
        )
        self.assertEqual(capture_page_bgr.await_count, 3)
        level_up_call = find_template_matches.call_args_list[0]
        matched_frame = level_up_call.args[0]
        self.assertEqual(matched_frame.shape, (720, 640))
        self.assertEqual(
            level_up_call.kwargs["threshold"],
            0.80,
        )

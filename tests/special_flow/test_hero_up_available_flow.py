import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.flows.hero_up_available import (  # noqa: E402
    BREAKTHROUGH_CLICK_POSITION,
    BREAKTHROUGH_MARK_REGION,
    BREAKTHROUGH_RECHECK_DELAY_MS,
    BREAKTHROUGH_REPEAT_DELAY_MS,
    HERO_ARROW_RIGHT_POSITION,
    HERO_CHANGE_SETTLE_MS,
    find_breakthrough_available,
    run_hero_up_available_flow,
)
from hauntedroom.runner.default_commands import FLOW_COMMANDS  # noqa: E402


AVAILABLE_FIXTURE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "special_flow" / "heroup_available.png"
)
UNAVAILABLE_FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "special_flow"
    / "heroup_un_available.png"
)


class HeroUpAvailableDetectionTest(TestCase):
    def test_detects_breakthrough_button_with_red_mark(self):
        frame = cv2.imread(str(AVAILABLE_FIXTURE_PATH))

        self.assertEqual(
            find_breakthrough_available(frame),
            BREAKTHROUGH_CLICK_POSITION,
        )

    def test_yellow_button_without_red_mark_is_unavailable(self):
        frame = cv2.imread(str(UNAVAILABLE_FIXTURE_PATH))

        self.assertIsNone(find_breakthrough_available(frame))

    def test_does_not_treat_lower_breakthrough_tab_as_available(self):
        frame = cv2.imread(str(AVAILABLE_FIXTURE_PATH))
        left, top, right, bottom = BREAKTHROUGH_MARK_REGION
        frame[top:bottom, left:right] = 0
        frame[640:680, 244:336] = (0, 255, 255)

        self.assertIsNone(find_breakthrough_available(frame))

    def test_rejects_unexpected_viewport_size(self):
        self.assertIsNone(
            find_breakthrough_available(np.zeros((100, 100, 3), dtype=np.uint8))
        )


class HeroUpAvailableFlowTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()

    @patch(
        "hauntedroom.flows.hero_up_available.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_clicks_repeatedly_moves_right_and_stops_on_ineligible_hero(
        self,
        capture_page_bgr,
    ):
        available = cv2.imread(str(AVAILABLE_FIXTURE_PATH))
        unavailable = cv2.imread(str(UNAVAILABLE_FIXTURE_PATH))
        capture_page_bgr.side_effect = [
            available,
            unavailable,
            available,
            unavailable,
            unavailable,
        ]
        operations = []

        async def record_click(x, y):
            operations.append(("click", x, y))

        async def record_wait(delay_ms):
            operations.append(("wait", delay_ms))

        self.page.mouse.click.side_effect = record_click
        self.page.wait_for_timeout.side_effect = record_wait

        completed = await run_hero_up_available_flow(self.page)

        self.assertTrue(completed)
        self.assertEqual(capture_page_bgr.await_count, 5)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(*BREAKTHROUGH_CLICK_POSITION),
                call(*BREAKTHROUGH_CLICK_POSITION),
                call(*HERO_ARROW_RIGHT_POSITION),
                call(*BREAKTHROUGH_CLICK_POSITION),
                call(*BREAKTHROUGH_CLICK_POSITION),
                call(*HERO_ARROW_RIGHT_POSITION),
            ],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [
                call(BREAKTHROUGH_REPEAT_DELAY_MS),
                call(BREAKTHROUGH_RECHECK_DELAY_MS),
                call(HERO_CHANGE_SETTLE_MS),
                call(BREAKTHROUGH_REPEAT_DELAY_MS),
                call(BREAKTHROUGH_RECHECK_DELAY_MS),
                call(HERO_CHANGE_SETTLE_MS),
            ],
        )
        self.assertEqual(
            operations,
            [
                ("click", *BREAKTHROUGH_CLICK_POSITION),
                ("wait", BREAKTHROUGH_REPEAT_DELAY_MS),
                ("click", *BREAKTHROUGH_CLICK_POSITION),
                ("wait", BREAKTHROUGH_RECHECK_DELAY_MS),
                ("click", *HERO_ARROW_RIGHT_POSITION),
                ("wait", HERO_CHANGE_SETTLE_MS),
                ("click", *BREAKTHROUGH_CLICK_POSITION),
                ("wait", BREAKTHROUGH_REPEAT_DELAY_MS),
                ("click", *BREAKTHROUGH_CLICK_POSITION),
                ("wait", BREAKTHROUGH_RECHECK_DELAY_MS),
                ("click", *HERO_ARROW_RIGHT_POSITION),
                ("wait", HERO_CHANGE_SETTLE_MS),
            ],
        )

    @patch(
        "hauntedroom.flows.hero_up_available.capture_page_bgr",
        new_callable=AsyncMock,
    )
    async def test_stop_event_ends_before_clicking(self, capture_page_bgr):
        stop_event = asyncio.Event()
        stop_event.set()

        completed = await run_hero_up_available_flow(self.page, stop_event)

        self.assertFalse(completed)
        capture_page_bgr.assert_not_awaited()
        self.page.mouse.click.assert_not_awaited()

    def test_flow_is_registered_as_shift_6(self):
        self.assertIn("6", FLOW_COMMANDS)
        self.assertEqual(
            FLOW_COMMANDS["6"].menu_label,
            "Hero breakthrough available",
        )

    @patch(
        "hauntedroom.runner.default_commands.reload_policy."
        "get_hero_up_available_flow"
    )
    async def test_shift_6_resolves_reloadable_flow(self, get_flow):
        flow = AsyncMock(return_value=True)
        get_flow.return_value = flow
        stop_event = asyncio.Event()

        resolved = FLOW_COMMANDS["6"].resolve([], True, None)
        completed = await resolved.run(self.page, stop_event, False)

        self.assertTrue(completed)
        get_flow.assert_called_once_with(True)
        flow.assert_awaited_once_with(self.page, stop_event)

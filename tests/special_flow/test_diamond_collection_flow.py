import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.template_matching import load_template  # noqa: E402
from hauntedroom.flows.diamond_collection import (  # noqa: E402
    DIAMOND_CLOSE_TEMPLATE_PATH,
    DIAMOND_REWARD_TEMPLATE_PATH,
    run_diamond_collection_flow,
)
from hauntedroom.flows.diamond_collection_vision import (  # noqa: E402
    find_diamond_content_mark,
    find_diamond_popup_close,
    find_diamond_popup_reward,
    find_diamond_tabs,
)


FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "special_flow"


class DiamondCollectionDetectorTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.close_template = load_template(DIAMOND_CLOSE_TEMPLATE_PATH)
        cls.reward_template = load_template(DIAMOND_REWARD_TEMPLATE_PATH)

    def test_collection_fixture_finds_tabs_and_first_content_mark(self):
        frame = cv2.imread(str(FIXTURE_DIR / "diamond_collection.png"))
        self.assertIsNotNone(frame)

        self.assertEqual(
            find_diamond_tabs(frame),
            [(0, 181, 655), (1, 273, 655), (2, 357, 655)],
        )
        self.assertEqual(find_diamond_content_mark(frame), (381, 164))

    def test_detail_fixture_finds_reward_and_foreground_close(self):
        frame = cv2.imread(str(FIXTURE_DIR / "diamond_collect_detail.png"))
        self.assertIsNotNone(frame)

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        reward = find_diamond_popup_reward(frame_gray, self.reward_template)
        self.assertIsNotNone(reward)
        self.assertEqual(reward[:2], (452, 236))
        self.assertGreaterEqual(reward[2], 0.90)
        close = find_diamond_popup_close(
            frame_gray, self.close_template
        )
        self.assertIsNotNone(close)
        self.assertEqual(close[:2], (478, 149))
        self.assertGreaterEqual(close[2], 0.90)

    def test_detectors_reject_invalid_frame_shapes(self):
        color = np.zeros((100, 100, 3), dtype=np.uint8)
        gray = np.zeros((100, 100), dtype=np.uint8)

        self.assertEqual(find_diamond_tabs(color), [])
        self.assertIsNone(find_diamond_content_mark(color))
        self.assertIsNone(find_diamond_popup_reward(gray, self.reward_template))
        self.assertIsNone(find_diamond_popup_close(gray, self.close_template))


class DiamondCollectionFlowTest(IsolatedAsyncioTestCase):
    def _page(self):
        page = Mock()
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        page.mouse.move = AsyncMock()
        page.mouse.wheel = AsyncMock()
        return page

    @patch(
        "hauntedroom.flows.diamond_collection.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.diamond_collection.capture_page_bgr",
        new_callable=AsyncMock,
        return_value=np.zeros((720, 640, 3), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.diamond_collection.find_diamond_popup_close")
    @patch("hauntedroom.flows.diamond_collection.find_diamond_popup_reward")
    @patch("hauntedroom.flows.diamond_collection.find_diamond_content_mark")
    @patch("hauntedroom.flows.diamond_collection.find_diamond_tabs")
    async def test_flow_opens_collects_closes_and_finishes(
        self,
        find_tabs,
        find_content,
        find_reward,
        find_close,
        _capture,
        _load,
    ):
        page = self._page()
        find_tabs.side_effect = [
            [(0, 181, 655)],
            [],
            [],
        ]
        find_content.side_effect = [(381, 164), None]
        find_reward.return_value = (452, 236, 1.0)
        find_close.return_value = (478, 149, 0.93)

        completed = await run_diamond_collection_flow(page, delay_ms=0)

        self.assertTrue(completed)
        self.assertEqual(
            page.mouse.click.await_args_list,
            [
                call(181, 655),
                call(381, 164),
                call(452, 236),
                call(452, 276),
                call(452, 276),
                call(478, 149),
            ],
        )
        page.mouse.wheel.assert_not_awaited()

    @patch(
        "hauntedroom.flows.diamond_collection.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.diamond_collection.capture_page_bgr",
        new_callable=AsyncMock,
        return_value=np.zeros((720, 640, 3), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.diamond_collection.find_diamond_content_mark",
        return_value=None,
    )
    @patch("hauntedroom.flows.diamond_collection.find_diamond_tabs")
    async def test_marked_tab_scrolls_until_its_badge_disappears(
        self,
        find_tabs,
        _find_content,
        _capture,
        _load,
    ):
        page = self._page()
        find_tabs.side_effect = [
            [(0, 181, 655)],
            [(0, 181, 655)],
            [],
            [],
        ]

        completed = await run_diamond_collection_flow(page, delay_ms=0)

        self.assertTrue(completed)
        page.mouse.click.assert_awaited_once_with(181, 655)
        page.mouse.move.assert_awaited_once_with(320, 500)
        page.mouse.wheel.assert_awaited_once_with(0, 527)

    @patch(
        "hauntedroom.flows.diamond_collection.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.diamond_collection.capture_page_bgr",
        new_callable=AsyncMock,
        return_value=np.zeros((720, 640, 3), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.diamond_collection.find_diamond_content_mark",
        return_value=None,
    )
    @patch(
        "hauntedroom.flows.diamond_collection.find_diamond_tabs",
        return_value=[],
    )
    async def test_no_marked_tabs_finishes_without_clicking(
        self,
        _find_tabs,
        _find_content,
        _capture,
        _load,
    ):
        page = self._page()

        completed = await run_diamond_collection_flow(page, delay_ms=0)

        self.assertTrue(completed)
        page.mouse.click.assert_not_awaited()

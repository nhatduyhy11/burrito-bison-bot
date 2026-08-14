import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.flows.exp_available import (  # noqa: E402
    EXP_CLICK_SETTLE_MS,
    find_exp_available_matches,
    run_exp_available_flow,
)


FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "special_flow"


class ExpAvailableDetectionTest(TestCase):
    def test_detects_all_exp_badges_in_first_fixture(self):
        frame = cv2.imread(str(FIXTURE_DIR / "exp_available.png"))

        matches = find_exp_available_matches(frame)

        self.assertEqual(
            matches,
            [
                (188, 208),
                (312, 208),
                (436, 208),
                (188, 352),
                (312, 352),
                (436, 352),
                (188, 496),
                (312, 496),
                (436, 496),
            ],
        )

    def test_detects_exp_badges_in_second_fixture(self):
        frame = cv2.imread(str(FIXTURE_DIR / "exp_available_2.png"))

        matches = find_exp_available_matches(frame)

        self.assertEqual(
            matches,
            [
                (188, 209),
                (312, 209),
                (436, 209),
                (188, 353),
                (312, 353),
            ],
        )

    def test_ignores_yellow_character_artwork(self):
        frame = cv2.imread(str(FIXTURE_DIR / "exp_avail_3.png"))

        matches = find_exp_available_matches(frame)

        self.assertEqual(
            matches,
            [
                (312, 208),
                (436, 208),
                (188, 352),
                (436, 352),
                (188, 496),
                (312, 496),
                (436, 496),
            ],
        )

    def test_ignores_orange_card_and_character_artwork(self):
        frame = cv2.imread(str(FIXTURE_DIR / "exp_avail_4.png"))

        matches = find_exp_available_matches(frame)

        self.assertEqual(
            matches,
            [
                (312, 359),
                (436, 359),
                (188, 503),
                (312, 503),
                (436, 503),
            ],
        )

    def test_ignores_dim_orange_card_background(self):
        frame = cv2.imread(str(FIXTURE_DIR / "exp_avail_5.png"))

        matches = find_exp_available_matches(frame)

        self.assertEqual(
            matches,
            [
                (312, 352),
                (436, 352),
                (188, 496),
                (312, 496),
                (436, 496),
            ],
        )

    def test_detects_exp_badges_after_grid_is_scrolled(self):
        frame = cv2.imread(str(FIXTURE_DIR / "exp_avail_scroll.png"))

        matches = find_exp_available_matches(frame)

        self.assertEqual(
            matches,
            [
                (188, 185),
                (312, 185),
                (436, 185),
                (188, 329),
                (312, 329),
                (436, 329),
            ],
        )


class ExpAvailableFlowTest(IsolatedAsyncioTestCase):
    @patch("hauntedroom.flows.exp_available.capture_page_bgr", new_callable=AsyncMock)
    async def test_clicks_first_match_waits_and_stops_when_no_match_remains(
        self, capture_page_bgr
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        first_frame = cv2.imread(str(FIXTURE_DIR / "exp_available.png"))
        empty_frame = np.zeros_like(first_frame)
        capture_page_bgr.side_effect = [first_frame, empty_frame]

        completed = await run_exp_available_flow(page)

        self.assertTrue(completed)
        self.assertEqual(capture_page_bgr.await_count, 2)
        page.mouse.click.assert_awaited_once_with(188, 208)
        page.wait_for_timeout.assert_awaited_once_with(EXP_CLICK_SETTLE_MS)

    @patch("hauntedroom.flows.exp_available.capture_page_bgr", new_callable=AsyncMock)
    async def test_stop_event_ends_before_clicking(self, capture_page_bgr):
        page = Mock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        stop_event = asyncio.Event()
        stop_event.set()

        completed = await run_exp_available_flow(page, stop_event)

        self.assertFalse(completed)
        capture_page_bgr.assert_not_awaited()
        page.mouse.click.assert_not_awaited()

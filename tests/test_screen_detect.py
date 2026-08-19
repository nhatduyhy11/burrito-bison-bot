import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.screen_detect import (  # noqa: E402
    ScreenName,
    detect_current_screen,
    detect_screen,
)


class ScreenDetectionTest(TestCase):
    CASES = (
        (
            "fixtures/hauntedroom-captures/map_win/rewards_v1.png",
            ScreenName.HOME,
        ),
        (
            "fixtures/hauntedroom-captures/retest/fail_reward_detect.png",
            ScreenName.HOME,
        ),
        ("fixtures/active_research_match.png", ScreenName.RESEARCH),
        ("fixtures/special_flow/artifact_avail.png", ScreenName.ARTIFACT),
        ("fixtures/special_flow/artifact_avail_2.png", ScreenName.ARTIFACT),
        ("fixtures/special_flow/exp_available.png", ScreenName.EXP_HERO),
        ("fixtures/special_flow/exp_available_2.png", ScreenName.EXP_HERO),
        ("fixtures/special_flow/exp_avail_scroll.png", ScreenName.EXP_HERO),
        (
            "fixtures/special_flow/heroup_available.png",
            ScreenName.HERO_AVAILABLE,
        ),
        (
            "fixtures/special_flow/heroup_un_available.png",
            ScreenName.HERO_AVAILABLE,
        ),
        ("fixtures/train_flow/train_available.png", ScreenName.TRAIN),
        ("fixtures/train_flow/train_reward.png", ScreenName.TRAIN),
        (
            "fixtures/hauntedroom-captures/boss_screen/final_boss_miss.png",
            ScreenName.AUTOMAP,
        ),
    )

    def test_detects_every_supported_screen_without_cross_matches(self):
        for relative_path, expected in self.CASES:
            with self.subTest(path=relative_path, expected=expected.value):
                frame = cv2.imread(str(PROJECT_ROOT / "tests" / relative_path))
                self.assertIsNotNone(frame)

                self.assertEqual(detect_screen(frame), expected)

    def test_returns_unknown_for_a_frame_without_any_anchor(self):
        frame = np.zeros((720, 640, 3), dtype=np.uint8)

        self.assertEqual(detect_screen(frame), ScreenName.UNKNOWN)

    def test_returns_unknown_for_invalid_frame_shape(self):
        frame = np.zeros((720, 640), dtype=np.uint8)

        self.assertEqual(detect_screen(frame), ScreenName.UNKNOWN)

    def test_returns_unknown_for_empty_frame(self):
        frame = np.empty((0, 0, 3), dtype=np.uint8)

        self.assertEqual(detect_screen(frame), ScreenName.UNKNOWN)


class CurrentScreenDetectionTest(IsolatedAsyncioTestCase):
    @patch(
        "hauntedroom.screen_detect.save_fallback_screenshot",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.screen_detect.capture_page_bgr", new_callable=AsyncMock)
    @patch("builtins.print")
    async def test_known_screen_does_not_save_a_fallback_screenshot(
        self,
        print_mock,
        capture_page_bgr,
        save_fallback_screenshot,
    ):
        frame = cv2.imread(
            str(
                PROJECT_ROOT
                / "tests"
                / "fixtures"
                / "special_flow"
                / "artifact_avail.png"
            )
        )
        capture_page_bgr.return_value = frame
        page = Mock()

        result = await detect_current_screen(page)

        self.assertEqual(result, ScreenName.ARTIFACT)
        capture_page_bgr.assert_awaited_once_with(page)
        print_mock.assert_called_once_with(
            "[screen_detect] screen=artifact",
            flush=True,
        )
        save_fallback_screenshot.assert_not_awaited()

    @patch(
        "hauntedroom.screen_detect.save_fallback_screenshot",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.screen_detect.capture_page_bgr", new_callable=AsyncMock)
    @patch("builtins.print")
    async def test_unknown_screen_saves_a_fallback_screenshot(
        self,
        print_mock,
        capture_page_bgr,
        save_fallback_screenshot,
    ):
        frame = np.zeros((720, 640, 3), dtype=np.uint8)
        capture_page_bgr.return_value = frame
        page = Mock()

        result = await detect_current_screen(page)

        self.assertEqual(result, ScreenName.UNKNOWN)
        capture_page_bgr.assert_awaited_once_with(page)
        print_mock.assert_called_once_with(
            "[screen_detect] screen=unknown",
            flush=True,
        )
        save_fallback_screenshot.assert_awaited_once_with(
            page,
            label="screen-detect-unknown",
        )

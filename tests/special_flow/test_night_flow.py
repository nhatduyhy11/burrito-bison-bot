import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, call, patch

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.flows.night import (
    NIGHT_BATTLE_CLICK,
    find_night_left_candle,
    find_night_solo_confirm,
    run_night_flow,
)

FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "night"


def fixture(name):
    return cv2.imread(str(FIXTURES / f"night-{name}.png"))


class NightVisionTest(TestCase):
    def test_lobby_candle_and_solo_popup_are_distinct(self):
        lobby, solo = fixture("lobby"), fixture("solo")
        self.assertEqual(find_night_left_candle(lobby), (239, 649))
        self.assertIsNone(find_night_solo_confirm(lobby))
        self.assertIsNone(find_night_left_candle(solo))
        self.assertEqual(find_night_solo_confirm(solo), (394, 464))

    def test_solo_requires_both_aligned_buttons(self):
        for region in ((180, 440, 310, 490), (330, 440, 460, 490)):
            with self.subTest(region=region):
                frame = fixture("solo")
                left, top, right, bottom = region
                frame[top:bottom, left:right] = 0
                self.assertIsNone(find_night_solo_confirm(frame))
        frame = fixture("solo")
        frame[450:500, 330:460] = frame[440:490, 330:460].copy()
        frame[440:450, 330:460] = 0
        self.assertIsNone(find_night_solo_confirm(frame))

    def test_unrelated_frames_have_no_candle_or_popup(self):
        paths = list((PROJECT_ROOT / "tests" / "fixtures" / "special_flow").glob("*.png"))
        for path in paths:
            with self.subTest(path=path.name):
                frame = cv2.imread(str(path))
                self.assertIsNone(find_night_left_candle(frame))
                self.assertIsNone(find_night_solo_confirm(frame))


class NightFlowTest(IsolatedAsyncioTestCase):
    @patch("hauntedroom.flows.night.click_and_wait", new_callable=AsyncMock)
    @patch("hauntedroom.flows.night.capture_page_bgr", new_callable=AsyncMock)
    async def test_retries_entry_and_solo_then_completes_exactly_twenty_returns(
        self, capture, click
    ):
        lobby, solo = fixture("lobby"), fixture("solo")
        battle = np.zeros_like(lobby)
        # Retry the candle, retry solo confirmation, retry candle after a
        # dismissed popup, then battle until the candle really returns.
        capture.side_effect = [lobby, lobby, solo, solo, lobby, battle, battle, lobby] + [
            frame for _ in range(19) for frame in (battle, lobby)
        ]
        click.return_value = True
        page = Mock()
        self.assertTrue(await run_night_flow(page))
        expected = [(239, 649), (239, 649), (394, 464), (394, 464),
                    (239, 649), NIGHT_BATTLE_CLICK, NIGHT_BATTLE_CLICK, (239, 649)]
        expected += [target for _ in range(18) for target in (NIGHT_BATTLE_CLICK, (239, 649))]
        expected += [NIGHT_BATTLE_CLICK]
        self.assertEqual(click.await_args_list, [call(page, target, 1000, None) for target in expected])
        self.assertEqual(capture.await_count, 46)

    @patch("hauntedroom.flows.night.click_and_wait", new_callable=AsyncMock)
    @patch("hauntedroom.flows.night.capture_page_bgr", new_callable=AsyncMock)
    async def test_stop_during_entry_popup_or_battle(self, capture, click):
        lobby, solo = fixture("lobby"), fixture("solo")
        battle = np.zeros_like(lobby)
        for frames in ([lobby], [lobby, solo], [lobby, battle]):
            with self.subTest(length=len(frames), last=frames[-1] is solo):
                capture.side_effect = frames
                click.side_effect = [True] * (len(frames) - 1) + [False]
                self.assertFalse(await run_night_flow(Mock()))

    @patch("hauntedroom.flows.night.capture_page_bgr", new_callable=AsyncMock)
    async def test_already_stopped_does_not_capture(self, capture):
        stop = asyncio.Event()
        stop.set()
        self.assertFalse(await run_night_flow(Mock(), stop))
        capture.assert_not_awaited()

    @patch("hauntedroom.flows.night.click_and_wait", new_callable=AsyncMock)
    @patch("hauntedroom.flows.night.capture_page_bgr", new_callable=AsyncMock)
    async def test_missing_initial_candle_does_not_tap_battle(self, capture, click):
        capture.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        self.assertFalse(await run_night_flow(Mock()))
        click.assert_not_awaited()

import sys
from asyncio import Event
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.actions.pause_exit import (
    click_pause_exit,
    find_pause_exit_button,
)


FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "hauntedroom-captures"
    / "cn_server"
    / "pause_map_exit.png"
)


class PauseExitVisionTest(TestCase):
    def test_cn_pause_popup_finds_red_exit_from_button_pair(self):
        image = cv2.imread(str(FIXTURE_PATH))

        button = find_pause_exit_button(image)

        self.assertIsNotNone(button)
        self.assertEqual(button.center, (251, 633))

    def test_red_button_without_yellow_neighbor_is_rejected(self):
        image = cv2.imread(str(FIXTURE_PATH))
        image[600:665, 320:465] = 0

        self.assertIsNone(find_pause_exit_button(image))

    def test_unrelated_red_and_yellow_components_are_rejected(self):
        image = np.zeros((720, 640, 3), dtype=np.uint8)
        image[610:645, 190:300] = (140, 20, 210)
        image[625:660, 340:450] = (0, 200, 255)

        self.assertIsNone(find_pause_exit_button(image))


class PauseExitActionTest(IsolatedAsyncioTestCase):
    async def test_clicks_detected_red_button_center(self):
        page = Mock()
        page.screenshot = AsyncMock(return_value=FIXTURE_PATH.read_bytes())
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock()
        page.mouse.click = AsyncMock()

        completed = await click_pause_exit(
            page=page,
            timeout_ms=1_000,
            poll_ms=100,
            delay_ms=0,
            label="Exit confirm",
            stop_event=Event(),
        )

        self.assertTrue(completed)
        page.mouse.click.assert_awaited_once_with(251, 633)

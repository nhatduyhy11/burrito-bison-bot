import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap import run_automap_flow
from hauntedroom.flows.automap_support.vision.build import (
    find_first_available_build_option,
)


class BuildTest(IsolatedAsyncioTestCase):

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
    def make_build_button(
        popup: np.ndarray,
        top: int,
        price_color: tuple[int, int, int],
    ) -> tuple[int, int]:
        left, width, height = 392, 78, 26
        popup[top : top + height, left : left + width] = (90, 215, 252)
        popup[top + 8 : top + 10, left + 48 : left + 58] = price_color
        return left + width // 2, top + height // 2

    def test_single_centered_white_build_option_is_available(self):
        popup = np.zeros((720, 640, 3), dtype=np.uint8)
        expected_click = self.make_build_button(popup, 361, (255, 255, 255))

        self.assertEqual(
            find_first_available_build_option(popup),
            expected_click,
        )

    def test_red_first_build_option_skips_to_white_second_option(self):
        popup = np.zeros((720, 640, 3), dtype=np.uint8)
        self.make_build_button(popup, 329, (0, 0, 255))
        expected_click = self.make_build_button(popup, 394, (255, 255, 255))

        self.assertEqual(
            find_first_available_build_option(popup),
            expected_click,
        )

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template", return_value=(0, 0, 0.0))
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_build_uses_highest_x_then_y_and_first_white_option(
        self,
        capture_page_bgr,
        find_template_matches,
        _find_template,
        _load_template,
    ):
        initial = np.zeros((720, 640, 3), dtype=np.uint8)
        popup = np.zeros_like(initial)
        option_click = self.make_build_button(popup, 361, (255, 255, 255))
        capture_page_bgr.side_effect = [initial, popup]

        def matches_for(_frame, _template, template_name, **_kwargs):
            if template_name == "built.png":
                return [
                    (300, 600, 0.95),
                    (500, 300, 0.91),
                    (500, 600, 0.90),
                ]
            return []

        find_template_matches.side_effect = matches_for
        stop_event = asyncio.Event()

        async def stop_after_option_click(*_args, **_kwargs):
            if self.page.mouse.click.await_count == 2:
                stop_event.set()

        self.page.mouse.click.side_effect = stop_after_option_click

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(500, 600), call(*option_click)],
        )

import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

import numpy as np

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.common import HOTKEY_SCRIPT, start_hotkey_listener
from hauntedroom.custom_macro import run_research_flow
from hauntedroom_runner import SKIP_TEMPLATE_MATCHED, run_actions, wait_for_template


class HauntedRoomRunnerTimeoutTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()

        self.template_path = Path("start.png")
        self.actions = [
            {
                "type": "click_template",
                "_template_path": self.template_path,
                "note": "Start",
                "delay_ms": 0,
            },
            {"type": "click", "x": 10, "y": 20},
        ]

    @patch(
        "hauntedroom_runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom_runner.wait_for_template", new_callable=AsyncMock)
    async def test_first_timeout_skips_rest_of_loop_then_retries(
        self, wait_for_template, _load_template
    ):
        wait_for_template.side_effect = [
            TimeoutError("first timeout"),
            (30, 40, 0.95),
        ]

        await run_actions(self.page, self.actions, loop_count=2)

        self.assertEqual(wait_for_template.await_count, 2)
        self.assertEqual(self.page.mouse.click.await_count, 2)

    @patch(
        "hauntedroom_runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom_runner.wait_for_template", new_callable=AsyncMock)
    async def test_second_timeout_stops_runner(
        self, wait_for_template, _load_template
    ):
        wait_for_template.side_effect = [
            TimeoutError("first timeout"),
            TimeoutError("second timeout"),
        ]

        with self.assertRaisesRegex(TimeoutError, "second timeout"):
            await run_actions(self.page, self.actions, loop_count=3)

        self.assertEqual(wait_for_template.await_count, 2)
        self.page.mouse.click.assert_not_awaited()

    @patch(
        "hauntedroom_runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom_runner.wait_for_template", new_callable=AsyncMock)
    async def test_successful_loop_resets_timeout_count(
        self, wait_for_template, _load_template
    ):
        wait_for_template.side_effect = [
            TimeoutError("first timeout"),
            (30, 40, 0.95),
            TimeoutError("timeout after recovery"),
            TimeoutError("consecutive timeout"),
        ]

        with self.assertRaisesRegex(TimeoutError, "consecutive timeout"):
            await run_actions(self.page, self.actions, loop_count=4)

        self.assertEqual(wait_for_template.await_count, 4)
        self.assertEqual(self.page.mouse.click.await_count, 2)

    @patch(
        "hauntedroom_runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom_runner.wait_for_template", new_callable=AsyncMock)
    async def test_click_template_skip_if_template_avoids_clicking_stale_step(
        self, wait_for_template, load_template
    ):
        skip_path = Path("home.png")
        self.actions[0]["_skip_if_template_path"] = skip_path
        wait_for_template.return_value = SKIP_TEMPLATE_MATCHED

        await run_actions(self.page, self.actions, loop_count=1)

        self.assertEqual(load_template.call_count, 2)
        wait_for_template.assert_awaited_once()
        self.assertIs(wait_for_template.await_args.args[-2], load_template.return_value)
        self.assertEqual(wait_for_template.await_args.args[-1], skip_path.name)
        self.page.mouse.click.assert_awaited_once_with(10, 20, button="left")

    @patch("hauntedroom_runner.capture_page_grayscale", new_callable=AsyncMock)
    @patch("hauntedroom_runner.find_template")
    async def test_wait_for_template_returns_skip_when_skip_template_matches(
        self, find_template, capture_page_grayscale
    ):
        capture_page_grayscale.return_value = np.zeros((10, 10), dtype=np.uint8)
        find_template.side_effect = [(0, 0, 0.4), (20, 30, 0.95)]

        result = await wait_for_template(
            self.page,
            np.zeros((1, 1), dtype=np.uint8),
            "exit_back.png",
            0.75,
            1000,
            400,
            skip_template=np.zeros((1, 1), dtype=np.uint8),
            skip_template_name="start_home.png",
        )

        self.assertIs(result, SKIP_TEMPLATE_MATCHED)
        self.page.wait_for_timeout.assert_not_awaited()


class HauntedRoomRunnerHotkeyTest(IsolatedAsyncioTestCase):
    async def test_stop_event_ends_flow_without_clicking(self):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        stop_event = asyncio.Event()
        stop_event.set()

        completed = await run_actions(
            page,
            [{"type": "click", "x": 10, "y": 20}],
            loop_count=None,
            stop_event=stop_event,
        )

        self.assertFalse(completed)
        page.mouse.click.assert_not_awaited()

    async def test_hotkey_listener_is_installed_for_current_and_future_frames(self):
        page = Mock()
        page.expose_binding = AsyncMock()
        page.add_init_script = AsyncMock()
        frame_one = Mock()
        frame_one.evaluate = AsyncMock()
        frame_two = Mock()
        frame_two.evaluate = AsyncMock()
        page.frames = [frame_one, frame_two]

        await start_hotkey_listener(page, asyncio.Queue())

        page.expose_binding.assert_awaited_once()
        page.add_init_script.assert_awaited_once_with(HOTKEY_SCRIPT)
        frame_one.evaluate.assert_awaited_once_with(HOTKEY_SCRIPT)
        frame_two.evaluate.assert_awaited_once_with(HOTKEY_SCRIPT)

    @patch(
        "hauntedroom.custom_macro.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.custom_macro.capture_page_grayscale", new_callable=AsyncMock)
    @patch("hauntedroom.custom_macro.find_template")
    async def test_research_flow_returns_to_available_after_active_is_gone(
        self,
        find_template,
        capture_page_grayscale,
        _load_template,
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        capture_page_grayscale.return_value = np.zeros((10, 10), dtype=np.uint8)
        find_template.side_effect = [
            (11, 22, 0.61),
            (33, 44, 0.62),
            (0, 0, 0.40),
            (55, 66, 0.63),
            (0, 0, 0.41),
            (0, 0, 0.42),
            (0, 0, 0.43),
            (0, 0, 0.44),
            (0, 0, 0.45),
            (0, 0, 0.46),
            (0, 0, 0.47),
            (0, 0, 0.48),
        ]

        completed = await run_research_flow(page)

        self.assertTrue(completed)
        self.assertEqual(find_template.call_count, 12)
        self.assertEqual(find_template.call_args_list[0].args[-1], "bottom_left")
        self.assertEqual(find_template.call_args_list[0].kwargs["scales"], (1.0,))
        self.assertEqual(len(find_template.call_args_list[1].args), 3)
        self.assertEqual(find_template.call_args_list[1].kwargs["scales"], (1.0,))
        self.assertEqual(find_template.call_args_list[8].args[-1], "bottom_left")
        self.assertEqual(
            page.mouse.click.await_args_list,
            [call(11, 22), call(33, 44), call(55, 66)],
        )

    @patch(
        "hauntedroom.custom_macro.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.custom_macro.capture_page_grayscale", new_callable=AsyncMock)
    @patch("hauntedroom.custom_macro.find_template")
    async def test_research_flow_checks_available_four_times_before_ending(
        self,
        find_template,
        capture_page_grayscale,
        _load_template,
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        capture_page_grayscale.return_value = np.zeros((10, 10), dtype=np.uint8)
        find_template.side_effect = [
            (0, 0, score) for score in (0.40, 0.41, 0.42, 0.43)
        ]

        completed = await run_research_flow(page)

        self.assertTrue(completed)
        self.assertEqual(find_template.call_count, 4)
        self.assertEqual(page.wait_for_timeout.await_count, 3)
        page.mouse.click.assert_not_awaited()

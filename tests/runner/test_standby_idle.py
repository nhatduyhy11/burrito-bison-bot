import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.runner.commands import FlowCommand
from hauntedroom.runner.default_commands import FLOW_COMMANDS
from hauntedroom.runner.standby import run_standby_controller
from hauntedroom.screen_detect import ScreenName


class StandbyIdleTest(IsolatedAsyncioTestCase):
    @patch(
        "hauntedroom.runner.standby.detect_current_screen",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_shift_8_saves_live_screenshot_and_accepts_the_next_command(
        self,
        start_hotkey_listener,
        save_live_screenshot,
        detect_current_screen,
    ):
        page = Mock()

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("8")
            command_queue.put_nowait("1")

        start_hotkey_listener.side_effect = enqueue_commands
        detect_current_screen.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(page, [], FLOW_COMMANDS, dev_reload=False)

        save_live_screenshot.assert_awaited_once_with(page)
        detect_current_screen.assert_awaited_once_with(page)

    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch(
        "hauntedroom.runner.standby.detect_current_screen",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_unknown_screen_stays_idle_and_accepts_the_next_command(
        self,
        start_hotkey_listener,
        detect_current_screen,
        save_live_screenshot,
    ):
        page = Mock()

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("1")
            command_queue.put_nowait("8")

        start_hotkey_listener.side_effect = enqueue_commands
        detect_current_screen.return_value = ScreenName.UNKNOWN
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(page, [], FLOW_COMMANDS, dev_reload=False)

        detect_current_screen.assert_awaited_once_with(page)
        save_live_screenshot.assert_awaited_once_with(page)

    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_resolver_failure_keeps_idle_and_accepts_the_next_command(
        self, start_hotkey_listener, save_live_screenshot
    ):
        page = Mock()
        resolve = Mock(side_effect=RuntimeError("reload failed"))
        command = FlowCommand("x", "test", "Test", resolve)

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("x")
            command_queue.put_nowait("8")

        start_hotkey_listener.side_effect = enqueue_commands
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(page, [], {"x": command})

        resolve.assert_called_once_with([], False, None)
        save_live_screenshot.assert_awaited_once_with(page)

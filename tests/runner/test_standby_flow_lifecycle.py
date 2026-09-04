import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.runtime import FlowControl
from hauntedroom.runner.commands import FlowCommand, ResolvedFlow
from hauntedroom.runner.default_commands import FLOW_COMMANDS
from hauntedroom.runner.reload import AutomapRuntime
from hauntedroom.runner.standby import run_standby_controller
from hauntedroom.screen_detect import ScreenName


class StandbyFlowLifecycleTest(IsolatedAsyncioTestCase):
    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch(
        "hauntedroom.runner.default_commands.start_auto.run_start_automap_loop",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.runner.default_commands.reload_policy.get_automap_runtime")
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    @patch(
        "hauntedroom.runner.standby.detect_current_screen",
        new_callable=AsyncMock,
    )
    async def test_auto_switched_home_flow_can_pause_resume_and_stop(
        self,
        detect_current_screen,
        start_hotkey_listener,
        get_automap_runtime,
        run_start_automap_loop,
        save_live_screenshot,
    ):
        page = Mock()
        started = asyncio.Event()
        resumed = asyncio.Event()
        observed_control = None
        get_automap_runtime.return_value = AutomapRuntime(AsyncMock(), AsyncMock())

        async def controllable_flow(
            _page,
            _start_actions,
            _automap,
            flow_control,
            _action_runner,
            _debug,
            **_kwargs,
        ):
            nonlocal observed_control
            observed_control = flow_control
            started.set()
            while await flow_control.checkpoint():
                if not flow_control.is_paused:
                    resumed.set()
                await asyncio.sleep(0)
            return False

        async def enqueue_commands(_page, command_queue):
            async def produce_commands():
                command_queue.put_nowait("1")
                await started.wait()
                resumed.clear()
                command_queue.put_nowait("1")
                while not observed_control.is_paused:
                    await asyncio.sleep(0)
                command_queue.put_nowait("1")
                await resumed.wait()
                command_queue.put_nowait("0")
                await observed_control.wait()
                command_queue.put_nowait("8")

            asyncio.create_task(produce_commands())

        start_hotkey_listener.side_effect = enqueue_commands
        detect_current_screen.return_value = ScreenName.HOME
        run_start_automap_loop.side_effect = controllable_flow
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(page, [], FLOW_COMMANDS)

        self.assertIsInstance(observed_control, FlowControl)
        self.assertTrue(observed_control.is_set())
        run_start_automap_loop.assert_awaited_once()

    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_completed_flow_returns_idle_and_accepts_the_next_command(
        self, start_hotkey_listener, save_live_screenshot
    ):
        page = Mock()
        flow_finished = asyncio.Event()
        run_flow = AsyncMock(return_value=True)
        resolved = ResolvedFlow([], run_flow)
        command = FlowCommand("x", "test", "Test", Mock(return_value=resolved))

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("x")

            async def continue_after_flow():
                await flow_finished.wait()
                await asyncio.sleep(0)
                command_queue.put_nowait("8")

            asyncio.create_task(continue_after_flow())

        async def complete_flow(*args):
            flow_finished.set()
            return True

        run_flow.side_effect = complete_flow
        start_hotkey_listener.side_effect = enqueue_commands
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(page, [], {"x": command})

        run_flow.assert_awaited_once()
        save_live_screenshot.assert_awaited_once_with(page)

    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_busy_runner_rejects_a_second_flow(
        self, start_hotkey_listener, save_live_screenshot
    ):
        page = Mock()
        started = asyncio.Event()
        second_resolve = Mock()

        async def run_until_stopped(_page, stop_event, _debug):
            started.set()
            await stop_event.wait()
            return False

        first_command = FlowCommand(
            "x",
            "first",
            "First",
            Mock(return_value=ResolvedFlow([], run_until_stopped)),
        )
        second_command = FlowCommand("y", "second", "Second", second_resolve)

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("x")

            async def continue_while_busy():
                await started.wait()
                command_queue.put_nowait("y")
                command_queue.put_nowait("8")

            asyncio.create_task(continue_while_busy())

        start_hotkey_listener.side_effect = enqueue_commands
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(
                page,
                [],
                {"x": first_command, "y": second_command},
            )

        second_resolve.assert_not_called()
        save_live_screenshot.assert_awaited_once_with(page)

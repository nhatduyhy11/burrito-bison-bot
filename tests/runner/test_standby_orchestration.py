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


class StandbyOrchestrationTest(IsolatedAsyncioTestCase):
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

    @patch("hauntedroom.runner.default_commands.reload_policy.load_actions")
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
    async def test_shift_1_on_home_starts_combined_loop_with_automap(
        self,
        detect_current_screen,
        start_hotkey_listener,
        get_automap_runtime,
        run_start_automap_loop,
        save_live_screenshot,
        load_actions,
    ):
        page = Mock()
        actions = [{"type": "test-action"}]
        automap_flow = AsyncMock()
        action_runner = AsyncMock()
        get_automap_runtime.return_value = AutomapRuntime(automap_flow, action_runner)

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("1")
            command_queue.put_nowait("8")

        async def wait_until_controller_stops(
            _page,
            _start_actions,
            _automap,
            stop_event,
            _action_runner,
            _debug,
            **_kwargs,
        ):
            await stop_event.wait()
            return False

        start_hotkey_listener.side_effect = enqueue_commands
        detect_current_screen.return_value = ScreenName.HOME
        run_start_automap_loop.side_effect = wait_until_controller_stops
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(
                page,
                actions,
                FLOW_COMMANDS,
                dev_reload=True,
            )

        get_automap_runtime.assert_called_once_with(True)
        run_start_automap_loop.assert_awaited_once()
        self.assertIs(run_start_automap_loop.await_args.args[0], page)
        self.assertEqual(len(run_start_automap_loop.await_args.args[1]), 3)
        self.assertIs(run_start_automap_loop.await_args.args[2], automap_flow)
        self.assertIs(run_start_automap_loop.await_args.args[4], action_runner)
        load_actions.assert_not_called()

    @patch("hauntedroom.runner.default_commands.reload_policy.load_actions")
    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.reload_policy.get_train_flow")
    @patch("hauntedroom.runner.default_commands.reload_policy.get_automap_runtime")
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_shift_t_starts_train_then_automap_flow(
        self,
        start_hotkey_listener,
        get_automap_runtime,
        get_train_flow,
        save_live_screenshot,
        load_actions,
    ):
        page = Mock()
        original_actions = [{"type": "old-action"}]
        automap_flow = AsyncMock()
        train_flow = AsyncMock()
        get_automap_runtime.return_value = AutomapRuntime(automap_flow, AsyncMock())
        get_train_flow.return_value = train_flow

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("t")
            command_queue.put_nowait("8")

        async def wait_until_stopped(_page, _automap, stop_event, _debug, **_kwargs):
            await stop_event.wait()
            return False

        start_hotkey_listener.side_effect = enqueue_commands
        train_flow.side_effect = wait_until_stopped
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(
                page,
                original_actions,
                FLOW_COMMANDS,
                dev_reload=True,
                actions_path=Path("tools/json_macro/macro.env.json"),
            )

        get_automap_runtime.assert_called_once_with(True)
        get_train_flow.assert_called_once_with(True)
        train_flow.assert_awaited_once()
        self.assertEqual(
            train_flow.await_args.args[:2],
            (page, automap_flow),
        )
        load_actions.assert_not_called()

    @patch("hauntedroom.runner.default_commands.reload_policy.load_actions")
    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.reload_policy.get_train_flow")
    @patch("hauntedroom.runner.default_commands.reload_policy.get_automap_runtime")
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    @patch(
        "hauntedroom.runner.standby.detect_current_screen",
        new_callable=AsyncMock,
    )
    async def test_shift_1_on_train_starts_train_then_automap_flow(
        self,
        detect_current_screen,
        start_hotkey_listener,
        get_automap_runtime,
        get_train_flow,
        save_live_screenshot,
        load_actions,
    ):
        page = Mock()
        automap_flow = AsyncMock()
        train_flow = AsyncMock()
        get_automap_runtime.return_value = AutomapRuntime(automap_flow, AsyncMock())
        get_train_flow.return_value = train_flow

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("1")
            command_queue.put_nowait("8")

        async def wait_until_stopped(_page, _automap, stop_event, _debug, **_kwargs):
            await stop_event.wait()
            return False

        start_hotkey_listener.side_effect = enqueue_commands
        detect_current_screen.return_value = ScreenName.TRAIN
        train_flow.side_effect = wait_until_stopped
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(
                page,
                [{"type": "old-action"}],
                FLOW_COMMANDS,
                dev_reload=True,
                actions_path=Path("tools/json_macro/macro.env.json"),
            )

        detect_current_screen.assert_awaited_once_with(page)
        get_automap_runtime.assert_called_once_with(True)
        get_train_flow.assert_called_once_with(True)
        train_flow.assert_awaited_once()
        self.assertEqual(train_flow.await_args.args[:2], (page, automap_flow))
        load_actions.assert_not_called()

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

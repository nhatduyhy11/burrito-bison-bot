import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.runner.default_commands import FLOW_COMMANDS
from hauntedroom.runner.reload import AutomapRuntime
from hauntedroom.runner.standby import run_standby_controller
from hauntedroom.screen_detect import ScreenName


class StandbyDispatchTest(IsolatedAsyncioTestCase):
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
    @patch("hauntedroom.runner.default_commands.reload_policy.get_train_ad_exit_flow")
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_shift_t_starts_train_ad_exit_flow(
        self,
        start_hotkey_listener,
        get_train_ad_exit_flow,
        save_live_screenshot,
        load_actions,
    ):
        page = Mock()
        original_actions = [{"type": "old-action"}]
        train_ad_exit_flow = AsyncMock()
        get_train_ad_exit_flow.return_value = train_ad_exit_flow

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("t")
            command_queue.put_nowait("8")

        async def wait_until_stopped(_page, stop_event, _debug, **_kwargs):
            await stop_event.wait()
            return False

        start_hotkey_listener.side_effect = enqueue_commands
        train_ad_exit_flow.side_effect = wait_until_stopped
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(
                page,
                original_actions,
                FLOW_COMMANDS,
                dev_reload=True,
                actions_path=Path("tools/json_macro/macro.env.json"),
            )

        get_train_ad_exit_flow.assert_called_once_with(True)
        train_ad_exit_flow.assert_awaited_once()
        self.assertEqual(
            train_ad_exit_flow.await_args.args[0],
            page,
        )
        load_actions.assert_not_called()

    @patch("hauntedroom.runner.default_commands.reload_policy.load_actions")
    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.reload_policy.get_train_ad_exit_flow")
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_shift_e_starts_train_immediate_exit_flow_without_pet_and_ad(
        self,
        start_hotkey_listener,
        get_train_ad_exit_flow,
        save_live_screenshot,
        load_actions,
    ):
        page = Mock()
        original_actions = [{"type": "old-action"}]
        train_ad_exit_flow = AsyncMock()
        get_train_ad_exit_flow.return_value = train_ad_exit_flow

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("e")
            command_queue.put_nowait("8")

        async def wait_until_stopped(
            _page,
            stop_event,
            _debug,
            *,
            pet_and_ad,
        ):
            self.assertFalse(pet_and_ad)
            await stop_event.wait()
            return False

        start_hotkey_listener.side_effect = enqueue_commands
        train_ad_exit_flow.side_effect = wait_until_stopped
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(
                page,
                original_actions,
                FLOW_COMMANDS,
                dev_reload=True,
                actions_path=Path("tools/json_macro/macro.env.json"),
            )

        get_train_ad_exit_flow.assert_called_once_with(True)
        train_ad_exit_flow.assert_awaited_once()
        self.assertEqual(train_ad_exit_flow.await_args.args[0], page)
        self.assertFalse(train_ad_exit_flow.await_args.kwargs["pet_and_ad"])
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

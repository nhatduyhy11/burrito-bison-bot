import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.actions.runner import run_actions
from hauntedroom.core.runtime import (
    FlowControl,
    HOTKEY_SCRIPT,
    LIVE_SCREENSHOT_DIR,
    start_hotkey_listener,
)
from hauntedroom.flows.click_loop import (
    CLICK_INTERVAL_MS,
    CLICK_POSITION,
    run_click_loop,
)
from hauntedroom.runner.default_commands import FLOW_COMMANDS
from hauntedroom.runner.reload import AutomapRuntime, get_automap_flow
from hauntedroom.runner.standby import (
    handle_control_command,
    run_standby_controller,
    validate_start_auto_hotkeys,
)


class StandbyControllerTest(IsolatedAsyncioTestCase):

    async def test_flow_control_pauses_resumes_and_stops_while_paused(self):
        control = FlowControl()

        self.assertTrue(control.pause())
        blocked_checkpoint = asyncio.create_task(control.checkpoint())
        await asyncio.sleep(0)
        self.assertFalse(blocked_checkpoint.done())

        self.assertTrue(control.resume())
        self.assertTrue(await blocked_checkpoint)

        self.assertTrue(control.pause())
        blocked_checkpoint = asyncio.create_task(control.checkpoint())
        await asyncio.sleep(0)
        control.set()

        self.assertFalse(await blocked_checkpoint)
        self.assertTrue(control.is_set())
        self.assertFalse(control.is_paused)

    async def test_flow_control_pauses_only_for_armed_boss_kind(self):
        control = FlowControl()

        self.assertTrue(control.pause_at_next_boss(final_only=True))
        self.assertEqual(
            control.boss_pause_target,
            FlowControl.PAUSE_AT_FINAL_BOSS,
        )
        self.assertFalse(control.pause_for_detected_boss(is_final_boss=False))
        self.assertFalse(control.is_paused)

        self.assertTrue(control.pause_for_detected_boss(is_final_boss=True))
        self.assertTrue(control.is_paused)
        self.assertIsNone(control.boss_pause_target)

    async def test_automap_hotkeys_arm_boss_pauses_for_shift_2_and_shift_3(self):
        for current_command in ("2", "3"):
            with self.subTest(current_command=current_command):
                control = FlowControl()
                page = Mock()
                flow_task = Mock()

                self.assertTrue(
                    await handle_control_command(
                        "2", page, flow_task, control, current_command
                    )
                )
                self.assertEqual(
                    control.boss_pause_target,
                    FlowControl.PAUSE_AT_ANY_BOSS,
                )

                self.assertTrue(
                    await handle_control_command(
                        "3", page, flow_task, control, current_command
                    )
                )
                self.assertEqual(
                    control.boss_pause_target,
                    FlowControl.PAUSE_AT_FINAL_BOSS,
                )

                self.assertTrue(
                    await handle_control_command(
                        "7", page, flow_task, control, current_command
                    )
                )
                self.assertEqual(
                    control.boss_pause_target,
                    FlowControl.PAUSE_AT_FINAL_BOSS,
                )

    async def test_automap_hotkeys_ignore_other_flows(self):
        control = FlowControl()

        self.assertFalse(
            await handle_control_command("2", Mock(), Mock(), control, "1")
        )
        self.assertIsNone(control.boss_pause_target)

    def test_shift_2_and_shift_3_use_the_same_flow_control(self):
        self.assertIs(FLOW_COMMANDS["2"].control_factory, FlowControl)
        self.assertIs(FLOW_COMMANDS["3"].control_factory, FlowControl)

    async def test_automap_hotkeys_can_be_remapped_by_config_values(self):
        remapped = {
            "pause_resume": "4",
            "pause_at_boss": "5",
            "pause_at_final_boss": "6",
            "stop": "7",
            "screenshot": "9",
        }

        for current_command in ("2", "3"):
            with self.subTest(current_command=current_command):
                control = FlowControl()
                self.assertTrue(
                    await handle_control_command(
                        "5",
                        Mock(),
                        Mock(),
                        control,
                        current_command,
                        remapped,
                    )
                )
                self.assertEqual(
                    control.boss_pause_target,
                    FlowControl.PAUSE_AT_ANY_BOSS,
                )

                # The old default is now unmapped and must be ignored.
                self.assertTrue(
                    await handle_control_command(
                        "2",
                        Mock(),
                        Mock(),
                        control,
                        current_command,
                        remapped,
                    )
                )
                self.assertEqual(
                    control.boss_pause_target,
                    FlowControl.PAUSE_AT_ANY_BOSS,
                )

    def test_start_auto_hotkey_config_rejects_duplicate_digits(self):
        with self.assertRaisesRegex(ValueError, "cannot assign one digit twice"):
            validate_start_auto_hotkeys(
                {
                    "pause_resume": "1",
                    "pause_at_boss": "1",
                    "pause_at_final_boss": "3",
                    "stop": "0",
                    "screenshot": "8",
                }
            )

    @patch("hauntedroom.runner.reload.reload_action_modules")
    @patch("hauntedroom.runner.reload.importlib.reload")
    def test_dev_reload_refreshes_support_modules_before_automap(
        self, reload_module, reload_action_modules
    ):
        from hauntedroom.flows import automap
        from hauntedroom.flows.automap_support import (
            boss_action,
            boss_detector,
            boss_flow,
            completion_flow,
            detectors,
            gear_action,
            gear_vision,
            hero_action,
            hero_levelup_vision,
            map_completion,
            upgrade_action,
        )
        from hauntedroom.flows.automap_support.completion_flow import (
            blocker,
            first_win,
            reward,
            state,
        )
        from hauntedroom import settings

        refreshed_flow = Mock()
        refreshed_automap = Mock(run_automap_flow=refreshed_flow)
        reload_module.side_effect = [
            settings,
            boss_detector,
            detectors,
            boss_action,
            gear_vision,
            gear_action,
            hero_levelup_vision,
            state,
            first_win,
            reward,
            blocker,
            completion_flow,
            map_completion,
            upgrade_action,
            hero_action,
            boss_flow,
            refreshed_automap,
        ]

        result = get_automap_flow(dev_reload=True)

        self.assertIs(result, refreshed_flow)
        reload_action_modules.assert_called_once_with()
        self.assertEqual(
            reload_module.call_args_list,
            [
                call(settings),
                call(boss_detector),
                call(detectors),
                call(boss_action),
                call(gear_vision),
                call(gear_action),
                call(hero_levelup_vision),
                call(state),
                call(first_win),
                call(reward),
                call(blocker),
                call(completion_flow),
                call(map_completion),
                call(upgrade_action),
                call(hero_action),
                call(boss_flow),
                call(automap),
            ],
        )

    @patch("hauntedroom.runner.reload.importlib.reload")
    def test_action_reload_refreshes_action_loader_and_runner(self, reload_module):
        from hauntedroom.actions import loader as actions_loader
        from hauntedroom.actions import runner as actions_runner
        from hauntedroom.control_events import blockers as control_blockers
        from hauntedroom.control_events import new_tab_blocker
        from hauntedroom.core import template, vision
        from hauntedroom.runner import reload as reload_policy

        refreshed_load_actions = Mock()
        refreshed_run_actions = Mock()
        refreshed_loader = Mock(load_actions=refreshed_load_actions)
        refreshed_runner = Mock(run_actions=refreshed_run_actions)
        reload_module.side_effect = [
            template,
            vision,
            new_tab_blocker,
            control_blockers,
            refreshed_loader,
            refreshed_runner,
        ]
        original_load_actions = reload_policy.load_actions
        original_run_actions = reload_policy.run_actions

        try:
            result = reload_policy.reload_action_modules()
            observed_load_actions = reload_policy.load_actions
            observed_run_actions = reload_policy.run_actions
        finally:
            reload_policy.load_actions = original_load_actions
            reload_policy.run_actions = original_run_actions

        self.assertIs(result, refreshed_run_actions)
        self.assertIs(observed_load_actions, refreshed_load_actions)
        self.assertIs(observed_run_actions, refreshed_run_actions)
        self.assertEqual(
            reload_module.call_args_list,
            [
                call(template),
                call(vision),
                call(new_tab_blocker),
                call(control_blockers),
                call(actions_loader),
                call(actions_runner),
            ],
        )

    @patch("hauntedroom.runner.reload.importlib.reload", side_effect=AssertionError)
    def test_normal_mode_does_not_reload(self, _reload_module):
        from hauntedroom.flows import automap

        self.assertIs(get_automap_flow(), automap.run_automap_flow)

    def test_hotkey_script_accepts_digits_and_y(self):
        self.assertIn("/^Digit[0-9]$/.test(event.code)", HOTKEY_SCRIPT)
        self.assertIn('event.code === "KeyY"', HOTKEY_SCRIPT)
        self.assertIn('? "y"', HOTKEY_SCRIPT)
        self.assertNotIn('event.code === "Minus"', HOTKEY_SCRIPT)

    def test_shift_y_is_registered_for_artifact_flow(self):
        self.assertEqual(FLOW_COMMANDS["y"].key, "Y")
        self.assertEqual(FLOW_COMMANDS["y"].name, "artifact")

    def test_shift_8_capture_directory_is_inside_test_fixtures(self):
        self.assertEqual(
            LIVE_SCREENSHOT_DIR,
            Path("tests/fixtures/hauntedroom-captures"),
        )

    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_shift_8_saves_live_screenshot_and_stays_idle(
        self,
        start_hotkey_listener,
        save_live_screenshot,
    ):
        page = Mock()

        async def enqueue_capture(_page, command_queue):
            command_queue.put_nowait("8")

        async def stop_after_capture(_page):
            raise RuntimeError("stop test loop")

        start_hotkey_listener.side_effect = enqueue_capture
        save_live_screenshot.side_effect = stop_after_capture

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(page, [], FLOW_COMMANDS, dev_reload=False)

        save_live_screenshot.assert_awaited_once_with(page)

    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.reload_policy.load_actions")
    @patch("hauntedroom.runner.default_commands.reload_policy.get_action_runner")
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_dev_reload_reloads_actions_file_before_shift_1(
        self,
        start_hotkey_listener,
        get_action_runner,
        load_actions,
        save_live_screenshot,
    ):
        page = Mock()
        original_actions = [{"type": "old-action"}]
        reloaded_actions = [{"type": "new-action"}]
        action_runner = AsyncMock(return_value=True)
        get_action_runner.return_value = action_runner
        load_actions.return_value = reloaded_actions

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("1")
            command_queue.put_nowait("8")

        start_hotkey_listener.side_effect = enqueue_commands
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(
                page,
                original_actions,
                FLOW_COMMANDS,
                dev_reload=True,
                actions_path=Path("tools/hauntedroom_actions.sample.json"),
            )

        get_action_runner.assert_called_once_with(True)
        load_actions.assert_called_once_with(Path("tools/hauntedroom_actions.sample.json"))
        action_runner.assert_awaited_once_with(
            page,
            reloaded_actions,
            loop_count=None,
            stop_event=action_runner.await_args.kwargs["stop_event"],
        )

    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.start_auto.run_start_automap_loop", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.reload_policy.get_automap_runtime")
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_shift_3_starts_combined_loop_with_automap(
        self,
        start_hotkey_listener,
        get_automap_runtime,
        run_start_automap_loop,
        save_live_screenshot,
    ):
        page = Mock()
        actions = [{"type": "test-action"}]
        automap_flow = AsyncMock()
        action_runner = AsyncMock()
        get_automap_runtime.return_value = AutomapRuntime(automap_flow, action_runner)

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("3")
            command_queue.put_nowait("8")

        async def wait_until_controller_stops(
            _page,
            _actions,
            _automap,
            stop_event,
            _action_runner,
            _debug,
        ):
            await stop_event.wait()
            return False

        start_hotkey_listener.side_effect = enqueue_commands
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
        self.assertIs(run_start_automap_loop.await_args.args[1], actions)
        self.assertIs(run_start_automap_loop.await_args.args[2], automap_flow)
        self.assertIs(run_start_automap_loop.await_args.args[4], action_runner)

    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.reload_policy.load_actions")
    @patch("hauntedroom.runner.default_commands.reload_policy.get_train_flow")
    @patch("hauntedroom.runner.default_commands.reload_policy.get_automap_runtime")
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_shift_4_starts_train_then_automap_flow(
        self,
        start_hotkey_listener,
        get_automap_runtime,
        get_train_flow,
        load_actions,
        save_live_screenshot,
    ):
        page = Mock()
        original_actions = [{"type": "old-action"}]
        reloaded_actions = [{"type": "new-action"}]
        automap_flow = AsyncMock()
        train_flow = AsyncMock()
        get_automap_runtime.return_value = AutomapRuntime(automap_flow, AsyncMock())
        get_train_flow.return_value = train_flow
        load_actions.return_value = reloaded_actions

        async def enqueue_commands(_page, command_queue):
            command_queue.put_nowait("4")
            command_queue.put_nowait("8")

        async def wait_until_stopped(
            _page, _actions, _automap, stop_event, _debug
        ):
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
                actions_path=Path("tools/hauntedroom_actions.sample.json"),
            )

        get_automap_runtime.assert_called_once_with(True)
        get_train_flow.assert_called_once_with(True)
        load_actions.assert_called_once_with(Path("tools/hauntedroom_actions.sample.json"))
        train_flow.assert_awaited_once()
        self.assertEqual(
            train_flow.await_args.args[:3],
            (page, reloaded_actions, automap_flow),
        )

    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.start_auto.run_start_automap_loop", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.reload_policy.get_automap_runtime")
    @patch("hauntedroom.runner.standby.start_hotkey_listener", new_callable=AsyncMock)
    async def test_shift_1_toggles_pause_and_resume_then_shift_0_stops(
        self,
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
            _page, _actions, _automap, flow_control, _action_runner, _debug
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
                command_queue.put_nowait("3")
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
        run_start_automap_loop.side_effect = controllable_flow
        save_live_screenshot.side_effect = RuntimeError("stop test loop")

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(page, [], FLOW_COMMANDS)

        self.assertIsInstance(observed_control, FlowControl)
        self.assertTrue(observed_control.is_set())
        run_start_automap_loop.assert_awaited_once()

    async def test_shift_7_clicks_fixed_position_every_second_until_stopped(self):
        page = Mock()
        page.evaluate = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        stop_event = asyncio.Event()

        async def stop_after_second_click(*_args):
            if page.mouse.click.await_count == 2:
                stop_event.set()

        page.mouse.click.side_effect = stop_after_second_click

        async def finish_interval(awaitable, **_kwargs):
            awaitable.close()
            raise asyncio.TimeoutError

        with patch("hauntedroom.flows.click_loop.asyncio.wait_for") as wait_for:
            wait_for.side_effect = finish_interval
            await run_click_loop(page, stop_event)

        self.assertEqual(CLICK_POSITION, (440, 500))
        self.assertEqual(CLICK_INTERVAL_MS, 1000)
        self.assertEqual(
            page.mouse.click.await_args_list,
            [call(440, 500), call(440, 500)],
        )
        self.assertEqual(wait_for.await_count, 1)
        self.assertEqual(wait_for.await_args.kwargs["timeout"], 1)

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

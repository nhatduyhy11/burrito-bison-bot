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
from hauntedroom.runner.default_commands import FLOW_COMMANDS, SCREEN_FLOW_COMMANDS
from hauntedroom.runner.reload import AutomapRuntime, get_automap_flow
from hauntedroom.screen_detect import ScreenName
from hauntedroom.runner.standby import (
    format_start_auto_control_guide,
    format_start_auto_hotkeys,
    handle_control_command,
    run_standby_controller,
    validate_start_auto_hotkeys,
)


class StandbyControllerTest(IsolatedAsyncioTestCase):

    def test_start_auto_hotkeys_format_each_control_on_its_own_line(self):
        self.assertEqual(
            format_start_auto_hotkeys(
                {
                    "pause_resume": "1",
                    "pause_at_boss": "2",
                    "pause_at_final_boss": "3",
                    "screenshot": "8",
                    "stop": "0",
                }
            ),
            "    Shift+1 pause/resume\n"
            "    Shift+2 pause at boss\n"
            "    Shift+3 pause at final boss\n"
            "    Shift+8 screenshot\n"
            "    Shift+0 stop",
        )

    def test_start_auto_control_guide_formats_each_control_on_its_own_line(self):
        self.assertEqual(
            format_start_auto_control_guide(
                {
                    "pause_resume": "1",
                    "pause_at_boss": "2",
                    "pause_at_final_boss": "3",
                    "screenshot": "8",
                    "stop": "0",
                }
            ),
            "Auto-map controls:\n"
            "  Shift+1 pause/resume\n"
            "  Shift+2 pause at boss\n"
            "  Shift+3 pause at final boss\n"
            "  Shift+8 screenshot\n"
            "  Shift+0 stop",
        )

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
        for current_command in (
            SCREEN_FLOW_COMMANDS[ScreenName.AUTOMAP],
            SCREEN_FLOW_COMMANDS[ScreenName.HOME],
        ):
            with self.subTest(current_command=current_command.name):
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
            await handle_control_command(
                "2", Mock(), Mock(), control, FLOW_COMMANDS["5"]
            )
        )
        self.assertIsNone(control.boss_pause_target)

    def test_auto_switch_automap_flows_use_the_same_flow_control(self):
        self.assertIs(
            SCREEN_FLOW_COMMANDS[ScreenName.AUTOMAP].control_factory,
            FlowControl,
        )
        self.assertIs(
            SCREEN_FLOW_COMMANDS[ScreenName.HOME].control_factory,
            FlowControl,
        )

    async def test_automap_hotkeys_can_be_remapped_by_config_values(self):
        remapped = {
            "pause_resume": "4",
            "pause_at_boss": "5",
            "pause_at_final_boss": "6",
            "stop": "7",
            "screenshot": "9",
        }

        for current_command in (
            SCREEN_FLOW_COMMANDS[ScreenName.AUTOMAP],
            SCREEN_FLOW_COMMANDS[ScreenName.HOME],
        ):
            with self.subTest(current_command=current_command.name):
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
            boss_flow,
            completion_flow,
            gear_action,
            hero_action,
            map_completion,
            upgrade_action,
        )
        from hauntedroom.flows.automap_support.completion_flow import (
            blocker,
            first_win,
            reward,
            state,
        )
        from hauntedroom.flows.automap_support.vision import (
            boss_controls as boss_controls_vision,
            boss_hp as boss_hp_vision,
            boss_progress as boss_progress_vision,
            build as build_vision,
            gear as gear_vision,
            hero_levelup as hero_levelup_vision,
        )
        from hauntedroom import settings

        refreshed_flow = Mock()
        refreshed_automap = Mock(run_automap_flow=refreshed_flow)
        reload_module.side_effect = [
            settings,
            boss_controls_vision,
            boss_hp_vision,
            boss_progress_vision,
            build_vision,
            gear_vision,
            hero_levelup_vision,
            boss_action,
            gear_action,
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
                call(boss_controls_vision),
                call(boss_hp_vision),
                call(boss_progress_vision),
                call(build_vision),
                call(gear_vision),
                call(hero_levelup_vision),
                call(boss_action),
                call(gear_action),
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
        from hauntedroom.core import template_detection, template_matching, vision
        from hauntedroom.runner import reload as reload_policy

        refreshed_load_actions = Mock()
        refreshed_run_actions = Mock()
        refreshed_loader = Mock(load_actions=refreshed_load_actions)
        refreshed_runner = Mock(run_actions=refreshed_run_actions)
        reload_module.side_effect = [
            template_matching,
            vision,
            template_detection,
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
                call(template_matching),
                call(vision),
                call(template_detection),
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

    def test_hotkey_script_accepts_digits_and_t_but_not_removed_letters(self):
        self.assertIn("/^Digit[0-9]$/.test(event.code)", HOTKEY_SCRIPT)
        self.assertNotIn('event.code === "KeyY"', HOTKEY_SCRIPT)
        self.assertNotIn('? "y"', HOTKEY_SCRIPT)
        self.assertNotIn('event.code === "KeyG"', HOTKEY_SCRIPT)
        self.assertNotIn('? "g"', HOTKEY_SCRIPT)
        self.assertIn('event.code === "KeyT"', HOTKEY_SCRIPT)
        self.assertIn('? "t"', HOTKEY_SCRIPT)
        self.assertNotIn('event.code === "Minus"', HOTKEY_SCRIPT)

    def test_replaced_hotkeys_are_only_available_through_auto_switch(self):
        self.assertEqual(set(FLOW_COMMANDS), {"t", "5"})
        self.assertEqual(FLOW_COMMANDS["t"].key, "T")
        self.assertEqual(FLOW_COMMANDS["t"].name, "train then auto-battle")
        self.assertEqual(FLOW_COMMANDS["5"].key, "5")
        self.assertEqual(FLOW_COMMANDS["5"].name, "JSON action loop")
        self.assertEqual(
            {
                screen: command.name
                for screen, command in SCREEN_FLOW_COMMANDS.items()
            },
            {
                ScreenName.HOME: "start-auto loop",
                ScreenName.RESEARCH: "research",
                ScreenName.ARTIFACT: "artifact",
                ScreenName.EXP_HERO: "EXP available",
                ScreenName.HERO_AVAILABLE: "hero breakthrough available",
                ScreenName.AUTOMAP: "auto-map battle",
            },
        )
        self.assertNotIn(ScreenName.TRAIN, SCREEN_FLOW_COMMANDS)
        self.assertNotIn(ScreenName.UNKNOWN, SCREEN_FLOW_COMMANDS)

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

    @patch(
        "hauntedroom.runner.standby.detect_current_screen",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom.runner.standby.start_hotkey_listener",
        new_callable=AsyncMock,
    )
    async def test_shift_1_detects_screen_and_stays_idle(
        self,
        start_hotkey_listener,
        detect_current_screen,
    ):
        page = Mock()

        async def enqueue_detect(_page, command_queue):
            command_queue.put_nowait("1")

        async def stop_after_detection(_page):
            raise RuntimeError("stop test loop")

        start_hotkey_listener.side_effect = enqueue_detect
        detect_current_screen.side_effect = stop_after_detection

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(page, [], FLOW_COMMANDS, dev_reload=False)

        detect_current_screen.assert_awaited_once_with(page)

    @patch("hauntedroom.runner.default_commands.reload_policy.load_actions")
    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.start_auto.run_start_automap_loop", new_callable=AsyncMock)
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
        self.assertEqual(len(run_start_automap_loop.await_args.args[1]), 4)
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

        async def wait_until_stopped(
            _page, _automap, stop_event, _debug
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

    @patch("hauntedroom.runner.standby.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom.runner.default_commands.start_auto.run_start_automap_loop", new_callable=AsyncMock)
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
            _page, _start_actions, _automap, flow_control, _action_runner, _debug
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

    @patch("hauntedroom.runner.default_commands.reload_policy.load_actions")
    @patch("hauntedroom.runner.default_commands.reload_policy.get_action_runner")
    async def test_shift_5_loads_json_and_runs_actions_forever(
        self, get_action_runner, load_actions
    ):
        page = Mock()
        stop_event = asyncio.Event()
        action_path = Path("tools/json_macro/macro.env.json")
        loaded_actions = [Mock(), Mock()]
        action_runner = AsyncMock(return_value=False)
        load_actions.return_value = loaded_actions
        get_action_runner.return_value = action_runner

        resolved = FLOW_COMMANDS["5"].resolve([], False, action_path)
        completed = await resolved.run(page, stop_event, False)

        self.assertFalse(completed)
        load_actions.assert_called_once_with(action_path)
        get_action_runner.assert_called_once_with(False)
        action_runner.assert_awaited_once_with(
            page,
            loaded_actions,
            loop_count=None,
            stop_event=stop_event,
        )

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

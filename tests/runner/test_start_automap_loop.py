import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import ANY, AsyncMock, Mock, call, patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.actions.models import (
    ClearBlockersAction,
    ClickHeroSelectBattleAction,
    ClickMapExitBackAction,
    ClickPauseExitAction,
    ClickTemplateAction,
)
from hauntedroom.core.runtime import FlowControl
from hauntedroom.core.terminal import ORANGE
from hauntedroom.flows.start_auto import (
    BETWEEN_MAPS_WAIT_MS,
    map_was_lost,
    run_start_automap_loop,
)
from hauntedroom.flows.automap_support.map.model_state import MapRunState
from hauntedroom.runner.commands import (
    build_spawn_exit_lvup_actions,
    build_start_battle_actions,
)


class StartAutomapLoopTest(IsolatedAsyncioTestCase):
    def test_start_actions_are_fixed_in_python(self):
        actions = build_start_battle_actions()
        self.assertEqual(len(actions), 3)
        self.assertIsInstance(actions[0], ClearBlockersAction)
        self.assertIsInstance(actions[1], ClickTemplateAction)
        self.assertEqual(actions[1].template_path.name, "start_home.png")
        self.assertIsInstance(actions[2], ClickHeroSelectBattleAction)
        self.assertEqual(
            actions[2].header_template_path.name,
            "hero_select_battle_banner_top.png",
        )
        self.assertEqual(actions[2].entry_template_path.name, "start_home.png")
        self.assertNotIn(
            "start_battle.png",
            {path.name for path in actions[2].blocker_paths},
        )

    def test_spawn_exit_uses_language_agnostic_pause_button_pair(self):
        actions = build_spawn_exit_lvup_actions()

        self.assertEqual(actions[3].region, (120, 125, 175, 175))
        self.assertIsInstance(actions[4], ClickPauseExitAction)
        self.assertEqual(actions[4].retry_template_path.name, "exit_click.png")
        self.assertEqual(actions[4].retry_template_region, (120, 125, 175, 175))
        self.assertIsInstance(actions[5], ClickMapExitBackAction)
        self.assertNotIn(
            "exit_confirm.png",
            {
                action.template_path.name
                for action in actions
                if isinstance(action, ClickTemplateAction)
            },
        )
        self.assertNotIn(
            "exit_back.png",
            {
                action.template_path.name
                for action in actions
                if isinstance(action, ClickTemplateAction)
            },
        )

    async def test_loss_detector_is_currently_a_false_placeholder(self):
        self.assertFalse(await map_was_lost(Mock()))

    @patch(
        "hauntedroom.flows.start_auto.wait_with_countdown",
        new_callable=AsyncMock,
    )
    @patch(
        "hauntedroom.flows.start_auto.map_was_lost",
        new_callable=AsyncMock,
    )
    async def test_loops_start_then_automap_until_loss(
        self,
        map_was_lost_mock,
        wait_with_countdown_mock,
    ):
        page = Mock()
        stop_event = asyncio.Event()
        automap_flow = AsyncMock(return_value=True)
        action_runner = AsyncMock(return_value=True)
        run_state = MapRunState()
        map_was_lost_mock.side_effect = [False, True]
        wait_with_countdown_mock.return_value = True

        completed = await run_start_automap_loop(
            page,
            build_start_battle_actions(),
            automap_flow,
            stop_event,
            action_runner,
            run_state=run_state,
        )

        self.assertTrue(completed)
        self.assertEqual(action_runner.await_count, 2)
        self.assertEqual(
            action_runner.await_args_list,
            [
                call(
                    page,
                    build_start_battle_actions(),
                    loop_count=2,
                    stop_event=stop_event,
                    stop_after_success=True,
                ),
                call(
                    page,
                    build_start_battle_actions(),
                    loop_count=2,
                    stop_event=stop_event,
                    stop_after_success=True,
                ),
            ],
        )
        self.assertEqual(
            automap_flow.await_args_list,
            [
                call(
                    page,
                    stop_event,
                    debug=False,
                    on_win=ANY,
                    run_state=run_state,
                ),
                call(
                    page,
                    stop_event,
                    debug=False,
                    on_win=ANY,
                    run_state=run_state,
                ),
            ],
        )
        wait_with_countdown_mock.assert_awaited_once_with(
            page,
            BETWEEN_MAPS_WAIT_MS,
            "Start-auto loop 1 cooldown",
            stop_event,
        )

    @patch(
        "hauntedroom.flows.start_auto.map_was_lost",
        new_callable=AsyncMock,
    )
    async def test_stops_when_automap_does_not_complete(
        self,
        map_was_lost_mock,
    ):
        action_runner = AsyncMock(return_value=True)
        automap_flow = AsyncMock(return_value=False)

        completed = await run_start_automap_loop(
            Mock(),
            build_start_battle_actions(),
            automap_flow,
            asyncio.Event(),
            action_runner,
            run_state=MapRunState(),
        )

        self.assertFalse(completed)
        map_was_lost_mock.assert_not_awaited()

    @patch(
        "hauntedroom.flows.start_auto.wait_with_countdown",
        new_callable=AsyncMock,
        return_value=True,
    )
    @patch(
        "hauntedroom.flows.start_auto.map_was_lost",
        new_callable=AsyncMock,
        side_effect=[False, False, True],
    )
    async def test_recorded_win_keeps_third_loop_running(
        self,
        _map_was_lost,
        _wait_with_countdown,
    ):
        async def complete_map(_page, _stop_event, **kwargs):
            if complete_map.call_count == 0:
                kwargs["on_win"]()
            complete_map.call_count += 1
            return True

        complete_map.call_count = 0
        automap_flow = AsyncMock(side_effect=complete_map)
        action_runner = AsyncMock(return_value=True)

        completed = await run_start_automap_loop(
            Mock(),
            build_start_battle_actions(),
            automap_flow,
            asyncio.Event(),
            action_runner,
            run_state=MapRunState(),
        )

        self.assertTrue(completed)
        self.assertEqual(automap_flow.await_count, 3)

    @patch(
        "hauntedroom.flows.start_auto.wait_with_countdown",
        new_callable=AsyncMock,
        return_value=True,
    )
    @patch(
        "hauntedroom.flows.start_auto.colorize",
        return_value="orange loss log",
    )
    @patch("builtins.print")
    @patch(
        "hauntedroom.flows.start_auto.map_was_lost",
        new_callable=AsyncMock,
        side_effect=[False, True],
    )
    async def test_missing_reward_arms_pause_at_first_boss_of_next_map(
        self,
        _map_was_lost,
        print_mock,
        colorize_mock,
        _wait_with_countdown,
    ):
        stop_event = FlowControl()

        async def complete_map(_page, flow_control, **_kwargs):
            if complete_map.call_count == 1:
                self.assertEqual(
                    flow_control.boss_pause_target,
                    FlowControl.PAUSE_AT_ANY_BOSS,
                )
            complete_map.call_count += 1
            return True

        complete_map.call_count = 0

        completed = await run_start_automap_loop(
            Mock(),
            build_start_battle_actions(),
            AsyncMock(side_effect=complete_map),
            stop_event,
            AsyncMock(return_value=True),
            run_state=MapRunState(),
        )

        self.assertTrue(completed)
        self.assertEqual(complete_map.call_count, 2)
        colorize_mock.assert_called_once_with(
            "Map completed without a detected win reward; treating it as a "
            "loss and arming a one-shot pause at the first boss of the next "
            "map.",
            ORANGE,
        )
        print_mock.assert_any_call("orange loss log", flush=True)

    @patch(
        "hauntedroom.flows.start_auto.wait_with_countdown",
        new_callable=AsyncMock,
        return_value=True,
    )
    @patch(
        "hauntedroom.flows.start_auto.map_was_lost",
        new_callable=AsyncMock,
        return_value=True,
    )
    async def test_detected_reward_does_not_arm_next_boss_pause(
        self,
        _map_was_lost,
        _wait_with_countdown,
    ):
        stop_event = FlowControl()

        async def complete_winning_map(_page, _flow_control, **kwargs):
            kwargs["on_win"]()
            return True

        completed = await run_start_automap_loop(
            Mock(),
            build_start_battle_actions(),
            AsyncMock(side_effect=complete_winning_map),
            stop_event,
            AsyncMock(return_value=True),
            run_state=MapRunState(),
        )

        self.assertTrue(completed)
        self.assertIsNone(stop_event.boss_pause_target)

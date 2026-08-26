import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.runtime import FlowControl
from hauntedroom.runner.default_commands import FLOW_COMMANDS, SCREEN_FLOW_COMMANDS
from hauntedroom.screen_detect import ScreenName


class CommandPolicyTest(IsolatedAsyncioTestCase):
    def test_auto_switch_automap_flows_use_the_same_flow_control(self):
        for screen in (
            ScreenName.AUTOMAP,
            ScreenName.HOME,
            ScreenName.NEW_ACCOUNT,
        ):
            with self.subTest(screen=screen):
                self.assertIs(
                    SCREEN_FLOW_COMMANDS[screen].control_factory,
                    FlowControl,
                )

    def test_direct_hotkeys_and_auto_switched_flows_are_configured(self):
        self.assertEqual(set(FLOW_COMMANDS), {"t", "5", "9"})
        self.assertEqual(FLOW_COMMANDS["t"].key, "T")
        self.assertEqual(FLOW_COMMANDS["t"].name, "train then auto-battle")
        self.assertEqual(FLOW_COMMANDS["5"].key, "5")
        self.assertEqual(FLOW_COMMANDS["5"].name, "JSON action loop")
        self.assertEqual(FLOW_COMMANDS["9"].key, "9")
        self.assertEqual(FLOW_COMMANDS["9"].name, "spawn_exit_lvup loop")
        self.assertEqual(
            {screen: command.name for screen, command in SCREEN_FLOW_COMMANDS.items()},
            {
                ScreenName.HOME: "start-auto loop",
                ScreenName.RESEARCH: "research",
                ScreenName.ARTIFACT: "artifact",
                ScreenName.DIAMOND_COLLECTION: "diamond collection",
                ScreenName.EXP_HERO: "EXP available",
                ScreenName.HERO_AVAILABLE: "hero breakthrough available",
                ScreenName.NEW_ACCOUNT: "new-account setup then auto-map",
                ScreenName.AUTOMAP: "auto-map battle",
            },
        )
        self.assertNotIn(ScreenName.TRAIN, SCREEN_FLOW_COMMANDS)
        self.assertNotIn(ScreenName.UNKNOWN, SCREEN_FLOW_COMMANDS)
        self.assertEqual(
            {
                screen
                for screen, command in SCREEN_FLOW_COMMANDS.items()
                if command.stops_on_repeat_screen_hotkey
            },
            {
                ScreenName.RESEARCH,
                ScreenName.ARTIFACT,
                ScreenName.DIAMOND_COLLECTION,
                ScreenName.EXP_HERO,
                ScreenName.HERO_AVAILABLE,
            },
        )

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

    @patch("hauntedroom.runner.default_commands.reload_policy.get_action_runner")
    async def test_shift_9_runs_fixed_spawn_exit_lvup_actions_forever(
        self, get_action_runner
    ):
        page = Mock()
        stop_event = asyncio.Event()
        action_runner = AsyncMock(return_value=False)
        get_action_runner.return_value = action_runner

        resolved = FLOW_COMMANDS["9"].resolve(
            [{"type": "unrelated-json-macro"}],
            False,
            Path("tools/json_macro/macro.env.json"),
        )
        completed = await resolved.run(page, stop_event, False)

        self.assertFalse(completed)
        self.assertEqual(len(resolved.actions), 7)
        self.assertEqual(
            [action.note for action in resolved.actions],
            [
                "Before Start HOME",
                "Start HOME",
                "Start Battle",
                "Exit click",
                "Exit confirm",
                "Exit Back",
                "After Exit Back",
            ],
        )
        get_action_runner.assert_called_once_with(False)
        action_runner.assert_awaited_once_with(
            page,
            resolved.actions,
            loop_count=None,
            stop_event=stop_event,
            loop_label="spawn_exit_lvup loop",
        )

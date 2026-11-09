import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.control_events.battle_speed import BattleSpeedStatus
from hauntedroom.core.browser_hook import HOTKEY_SCRIPT
from hauntedroom.runner import speed_control
from hauntedroom.runner.speed_control import BattleSpeedController
from hauntedroom.screen_detect import ScreenName

MODULE = "hauntedroom.runner.speed_control"


def status(in_battle: bool) -> BattleSpeedStatus:
    return BattleSpeedStatus(in_battle, 3 if in_battle else None, 1.6, True)


class BattleSpeedControllerTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.frame = object()
        self.patches = {
            "find": patch(f"{MODULE}.find_game_frame", AsyncMock(return_value=self.frame)),
            "apply": patch(
                f"{MODULE}.apply_battle_speed",
                AsyncMock(return_value={"applied": True, "before": 1, "timeScale": 1.6}),
            ),
            "restore": patch(
                f"{MODULE}.restore_battle_speed",
                AsyncMock(return_value={"restored": True, "speed": 1}),
            ),
            "read": patch(f"{MODULE}.read_battle_speed", AsyncMock(return_value=status(True))),
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}
        self.addCleanup(patch.stopall)

    def controller(self, screen=ScreenName.AUTOMAP, interval_s=0.01):
        return BattleSpeedController(
            object(), interval_s=interval_s, detect_screen=AsyncMock(return_value=screen)
        )

    def test_hotkey_script_maps_brackets(self):
        self.assertIn('event.code === "BracketRight"', HOTKEY_SCRIPT)
        self.assertIn('event.code === "BracketLeft"', HOTKEY_SCRIPT)

    async def test_enable_outside_battle_does_nothing(self):
        controller = self.controller(screen=ScreenName.HOME)
        self.assertTrue(await controller.handle_command("]"))
        self.mocks["apply"].assert_not_awaited()
        self.assertFalse(controller.active)

    async def test_enable_then_hotkey_disable_restores(self):
        controller = self.controller(interval_s=60)
        await controller.handle_command("]")
        self.mocks["apply"].assert_awaited_once_with(
            self.frame, speed_control.DEFAULT_SPEED_SCALE
        )
        self.assertTrue(controller.active)

        await controller.handle_command("[")
        self.mocks["restore"].assert_awaited_once_with(self.frame)
        self.assertFalse(controller.active)

    async def test_watcher_restores_when_battle_ends(self):
        self.mocks["read"].side_effect = [status(True), status(False)]
        controller = self.controller()
        await controller.enable()
        for _ in range(50):
            if not controller.active:
                break
            await asyncio.sleep(0.01)
        self.assertFalse(controller.active)
        self.mocks["restore"].assert_awaited_once_with(self.frame)
        # Initial apply + one re-apply while still in battle.
        self.assertEqual(self.mocks["apply"].await_count, 2)

    async def test_not_applied_keeps_controller_off(self):
        self.mocks["apply"].return_value = {"applied": False, "reason": "battle type 7"}
        controller = self.controller()
        await controller.enable()
        self.assertFalse(controller.active)
        await controller.disable("hotkey")
        self.mocks["restore"].assert_not_awaited()

    async def test_other_commands_are_not_handled(self):
        self.assertFalse(await self.controller().handle_command("1"))
        self.assertEqual(speed_control.SPEED_ON_COMMAND, "]")

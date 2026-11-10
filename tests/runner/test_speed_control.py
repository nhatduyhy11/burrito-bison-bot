import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.browser_hook import HOTKEY_SCRIPT
from hauntedroom.runner.speed_control import BattleSpeedController
from hauntedroom.runner.default_commands import FLOW_DEFINITIONS

MODULE = "hauntedroom.runner.speed_control"


class BattleSpeedControllerTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.frame = object()
        self.patches = {
            "find": patch(f"{MODULE}.find_game_frame", AsyncMock(return_value=self.frame)),
            "apply": patch(f"{MODULE}.apply_battle_speed", AsyncMock(return_value={"applied": True})),
            "restore": patch(f"{MODULE}.restore_battle_speed", AsyncMock()),
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}
        self.addCleanup(patch.stopall)
        self.controller = BattleSpeedController(object(), interval_s=60)
        self.addAsyncCleanup(self.controller.disable, "test cleanup")

    def test_hotkeys_and_battle_flow_scope(self):
        self.assertIn('? "]"', HOTKEY_SCRIPT)
        self.assertIn('? "["', HOTKEY_SCRIPT)
        for name in ("automap", "start_auto", "train", "train_ad_exit", "new_account"):
            self.assertTrue(FLOW_DEFINITIONS[name].enters_battle, name)
        for name in ("research", "artifact", "exp_available", "hero_up_available"):
            self.assertFalse(FLOW_DEFINITIONS[name].enters_battle, name)

    async def test_arm_idle_then_apply_on_flow_and_restore_on_idle(self):
        await self.controller.handle_command("]")
        self.mocks["apply"].assert_not_awaited()
        await self.controller.set_battle_flow(True)
        self.mocks["apply"].assert_awaited_once_with(self.frame, 2.2)
        await self.controller.set_battle_flow(False)
        self.mocks["restore"].assert_awaited_once_with(self.frame)
        self.assertFalse(self.controller.active)
        # Preference survives idle, but no modifier runs until another battle flow.
        await self.controller.set_battle_flow(True)
        self.assertEqual(self.mocks["apply"].await_count, 2)

    async def test_non_battle_flow_never_applies(self):
        await self.controller.set_battle_flow(False)
        await self.controller.handle_command("]")
        self.mocks["find"].assert_not_awaited()
        self.assertFalse(self.controller.active)

    async def test_repeated_enable_applies_without_duplicate_watcher(self):
        await self.controller.set_battle_flow(True)
        await self.controller.handle_command("]")
        watcher = self.controller._watcher
        await self.controller.handle_command("]")
        self.assertIs(self.controller._watcher, watcher)
        self.assertEqual(self.mocks["apply"].await_count, 2)
        await self.controller.handle_command("[")
        self.assertFalse(self.controller.enabled)
        self.assertFalse(self.controller.active)
        self.mocks["restore"].assert_awaited_once()

    async def test_watcher_survives_gap_between_battles_and_retries(self):
        self.controller._interval_s = 0.001
        next_battle = asyncio.Event()
        calls = 0

        async def apply(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"applied": True}
            if calls == 2:
                return {"applied": False, "reason": "no battle"}
            if calls == 3:
                raise RuntimeError("frame detached")
            next_battle.set()
            return {"applied": True}

        self.mocks["apply"].side_effect = apply
        await self.controller.set_battle_flow(True)
        await self.controller.handle_command("]")
        await asyncio.wait_for(next_battle.wait(), 1)
        self.assertTrue(self.controller.active)
        self.assertGreaterEqual(self.mocks["find"].await_count, 2)
        self.mocks["restore"].assert_not_awaited()

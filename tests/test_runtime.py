import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.runtime import FlowControl


class RuntimeTest(IsolatedAsyncioTestCase):
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

    async def test_standby_clears_on_boss_pause_resume_stop_and_policy_change(self):
        for is_final in (False, True):
            control = FlowControl()
            self.assertTrue(control.standby_at_next_boss())
            self.assertTrue(await control.checkpoint())
            self.assertTrue(control.pause_for_detected_boss(is_final_boss=is_final))
            self.assertTrue(control.is_paused)
            self.assertFalse(control.is_boss_standby)
            self.assertTrue(control.resume())
            self.assertFalse(control.is_boss_standby)

        control = FlowControl()
        control.standby_at_next_boss()
        control.pause_at_next_boss(final_only=True)
        self.assertFalse(control.is_boss_standby)
        self.assertFalse(control.boss_pause_matches(is_final_boss=False))
        control.standby_at_next_boss()
        control.set()
        self.assertFalse(control.is_boss_standby)
        self.assertIsNone(control.boss_pause_target)

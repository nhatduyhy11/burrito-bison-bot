import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.runtime import HOTKEY_SCRIPT, FlowControl, start_hotkey_listener


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

    def test_hotkey_script_accepts_digits_and_t_but_not_removed_letters(self):
        self.assertIn("/^Digit[0-9]$/.test(event.code)", HOTKEY_SCRIPT)
        self.assertNotIn('event.code === "KeyY"', HOTKEY_SCRIPT)
        self.assertNotIn('? "y"', HOTKEY_SCRIPT)
        self.assertNotIn('event.code === "KeyG"', HOTKEY_SCRIPT)
        self.assertNotIn('? "g"', HOTKEY_SCRIPT)
        self.assertIn('event.code === "KeyT"', HOTKEY_SCRIPT)
        self.assertIn('? "t"', HOTKEY_SCRIPT)
        self.assertNotIn('event.code === "Minus"', HOTKEY_SCRIPT)

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

import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.browser_hook import (
    CLICK_LOGGER_SCRIPT,
    HOTKEY_SCRIPT,
    SUPPRESS_NEXT_CLICK_LOG_SCRIPT,
    start_hotkey_listener,
    start_user_click_logger,
    suppress_next_click_log,
)


class BrowserHookTest(IsolatedAsyncioTestCase):
    def test_hotkey_script_accepts_digits_t_and_e_but_not_removed_letters(self):
        self.assertIn("/^Digit[0-9]$/.test(event.code)", HOTKEY_SCRIPT)
        self.assertNotIn('event.code === "KeyY"', HOTKEY_SCRIPT)
        self.assertNotIn('? "y"', HOTKEY_SCRIPT)
        self.assertNotIn('event.code === "KeyG"', HOTKEY_SCRIPT)
        self.assertNotIn('? "g"', HOTKEY_SCRIPT)
        self.assertIn('event.code === "KeyT"', HOTKEY_SCRIPT)
        self.assertIn('? "t"', HOTKEY_SCRIPT)
        self.assertIn('event.code === "KeyE"', HOTKEY_SCRIPT)
        self.assertIn('? "e"', HOTKEY_SCRIPT)
        self.assertNotIn('event.code === "Minus"', HOTKEY_SCRIPT)

    async def test_hotkey_listener_is_installed_for_current_and_future_frames(self):
        page = Mock()
        page.expose_binding = AsyncMock()
        page.add_init_script = AsyncMock()
        frame_one = Mock(evaluate=AsyncMock())
        frame_two = Mock(evaluate=AsyncMock())
        page.frames = [frame_one, frame_two]

        await start_hotkey_listener(page, asyncio.Queue())

        page.expose_binding.assert_awaited_once()
        page.add_init_script.assert_awaited_once_with(HOTKEY_SCRIPT)
        frame_one.evaluate.assert_awaited_once_with(HOTKEY_SCRIPT)
        frame_two.evaluate.assert_awaited_once_with(HOTKEY_SCRIPT)

    async def test_click_logger_installs_binding_and_page_hook(self):
        page = Mock(expose_binding=AsyncMock(), evaluate=AsyncMock())

        await start_user_click_logger(page)

        page.expose_binding.assert_awaited_once()
        page.evaluate.assert_awaited_once_with(CLICK_LOGGER_SCRIPT)

    async def test_click_log_suppression_uses_hook_owned_page_state(self):
        page = Mock(evaluate=AsyncMock())

        await suppress_next_click_log(page)

        page.evaluate.assert_awaited_once_with(SUPPRESS_NEXT_CLICK_LOG_SCRIPT)

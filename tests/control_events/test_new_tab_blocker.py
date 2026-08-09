import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.control_events.new_tab_blocker import (
    ENABLE_SCRIPT_INJECTION,
    GAME_CORE_FRAME_GUARD_DELAY_MS,
    GAME_CORE_FRAME_GUARD_SCRIPT,
    PROFILE_POPUP_GUARD_SCRIPT,
    close_profile_popup_tabs,
    install_game_core_frame_guard,
    install_game_core_frame_guard_after_delay,
    install_profile_popup_guard,
    is_profile_popup_url,
)


class NewTabBlockerTest(IsolatedAsyncioTestCase):

    def test_profile_popup_url_match_is_narrow(self):
        self.assertTrue(
            is_profile_popup_url(
                "https://cp.hhgame.vn/v2/user/profile/123?source=game"
            )
        )
        self.assertFalse(is_profile_popup_url("https://cp.hhgame.vn/v2/user/login"))
        self.assertFalse(
            is_profile_popup_url("https://evil.example/v2/user/profile/123")
        )

    async def test_no_profile_popup_does_not_inject_css(self):
        game_page = Mock()
        game_page.url = "https://h5sdk.joynetgame.com/index.html"
        game_page.evaluate = AsyncMock()
        game_page.bring_to_front = AsyncMock()
        game_page.context = Mock(pages=[game_page])

        closed = await close_profile_popup_tabs(game_page)

        self.assertEqual(closed, 0)
        game_page.evaluate.assert_not_awaited()
        game_page.bring_to_front.assert_not_awaited()

    async def test_close_profile_popup_restores_and_updates_game_page(self):
        game_page = Mock()
        game_page.url = "https://h5sdk.joynetgame.com/index.html"
        game_page.evaluate = AsyncMock()
        game_page.bring_to_front = AsyncMock()
        profile_page = Mock()
        profile_page.url = "https://cp.hhgame.vn/v2/user/profile/123"
        profile_page.close = AsyncMock()
        unrelated_page = Mock()
        unrelated_page.url = "https://example.com/"
        game_page.context = Mock(pages=[game_page, profile_page, unrelated_page])

        closed = await close_profile_popup_tabs(game_page, "test blocker")

        self.assertEqual(closed, 1)
        profile_page.close.assert_awaited_once_with()
        game_page.evaluate.assert_not_awaited()
        game_page.bring_to_front.assert_awaited_once_with()

    async def test_install_guard_covers_current_and_future_documents(self):
        page = Mock()
        page.add_init_script = AsyncMock()
        first_frame = Mock(evaluate=AsyncMock())
        second_frame = Mock(evaluate=AsyncMock())
        page.frames = [first_frame, second_frame]

        await install_profile_popup_guard(page)

        page.add_init_script.assert_awaited_once_with(PROFILE_POPUP_GUARD_SCRIPT)
        first_frame.evaluate.assert_awaited_once_with(PROFILE_POPUP_GUARD_SCRIPT)
        second_frame.evaluate.assert_awaited_once_with(PROFILE_POPUP_GUARD_SCRIPT)

    async def test_profile_popup_guard_can_skip_script_injection(self):
        page = Mock()
        page.add_init_script = AsyncMock()
        page.frames = [Mock(evaluate=AsyncMock())]

        with patch(
            "hauntedroom.control_events.new_tab_blocker.ENABLE_SCRIPT_INJECTION",
            False,
        ):
            await install_profile_popup_guard(page)

        page.add_init_script.assert_not_awaited()
        page.frames[0].evaluate.assert_not_awaited()

    async def test_install_game_core_guard_injects_css_into_top_document(self):
        page = Mock()
        page.evaluate = AsyncMock()

        await install_game_core_frame_guard(page)

        page.evaluate.assert_awaited_once_with(GAME_CORE_FRAME_GUARD_SCRIPT)

    async def test_game_core_guard_can_skip_script_injection(self):
        page = Mock()
        page.evaluate = AsyncMock()

        with patch(
            "hauntedroom.control_events.new_tab_blocker.ENABLE_SCRIPT_INJECTION",
            False,
        ):
            await install_game_core_frame_guard(page)

        page.evaluate.assert_not_awaited()

    async def test_game_core_guard_is_injected_after_startup_delay(self):
        page = Mock()
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock()

        with patch("builtins.print") as print_mock:
            await install_game_core_frame_guard_after_delay(page)

        page.wait_for_timeout.assert_awaited_once_with(
            GAME_CORE_FRAME_GUARD_DELAY_MS
        )
        page.evaluate.assert_awaited_once_with(GAME_CORE_FRAME_GUARD_SCRIPT)
        print_mock.assert_called_once_with(
            f"iframe guard: injected CSS after {GAME_CORE_FRAME_GUARD_DELAY_MS}ms; "
            "#hwssH5GameCoreframe hidden",
            flush=True,
        )

    async def test_delayed_game_core_guard_can_skip_script_injection(self):
        page = Mock()
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock()

        with patch(
            "hauntedroom.control_events.new_tab_blocker.ENABLE_SCRIPT_INJECTION",
            False,
        ):
            await install_game_core_frame_guard_after_delay(page)

        page.wait_for_timeout.assert_not_awaited()
        page.evaluate.assert_not_awaited()

    def test_script_injection_is_enabled_by_default(self):
        self.assertTrue(ENABLE_SCRIPT_INJECTION)

    def test_game_core_guard_uses_idempotent_visibility_css(self):
        self.assertIn("haunted-room-hide-hwss-frame", GAME_CORE_FRAME_GUARD_SCRIPT)
        self.assertIn(
            "#hwssH5GameCoreframe{visibility:hidden!important}",
            GAME_CORE_FRAME_GUARD_SCRIPT,
        )
        self.assertNotIn("MutationObserver", GAME_CORE_FRAME_GUARD_SCRIPT)
        self.assertNotIn("postMessage", GAME_CORE_FRAME_GUARD_SCRIPT)
        self.assertNotIn("van-overflow-hidden", GAME_CORE_FRAME_GUARD_SCRIPT)
        self.assertNotIn("pointer-events", GAME_CORE_FRAME_GUARD_SCRIPT)
        self.assertNotIn("display", GAME_CORE_FRAME_GUARD_SCRIPT)

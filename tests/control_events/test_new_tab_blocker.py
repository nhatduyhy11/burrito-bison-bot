import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.control_events.new_tab_blocker import (
    GAME_CORE_FRAME_GUARD_SCRIPT,
    PROFILE_POPUP_GUARD_SCRIPT,
    close_profile_popup_tabs,
    install_game_core_frame_guard,
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

    async def test_install_game_core_guard_covers_current_and_future_documents(self):
        page = Mock()
        page.add_init_script = AsyncMock()
        first_frame = Mock(evaluate=AsyncMock())
        second_frame = Mock(evaluate=AsyncMock())
        page.frames = [first_frame, second_frame]

        await install_game_core_frame_guard(page)

        page.add_init_script.assert_awaited_once_with(GAME_CORE_FRAME_GUARD_SCRIPT)
        first_frame.evaluate.assert_awaited_once_with(GAME_CORE_FRAME_GUARD_SCRIPT)
        second_frame.evaluate.assert_awaited_once_with(GAME_CORE_FRAME_GUARD_SCRIPT)

    def test_game_core_guard_reapplies_important_inline_styles(self):
        self.assertIn("MutationObserver", GAME_CORE_FRAME_GUARD_SCRIPT)
        self.assertIn('setProperty("display", "none", "important")', GAME_CORE_FRAME_GUARD_SCRIPT)
        self.assertIn('attributeFilter: ["id", "class", "style"]', GAME_CORE_FRAME_GUARD_SCRIPT)

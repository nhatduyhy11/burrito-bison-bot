import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, call, patch

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.runner.navigation import navigate_to_game


class NavigateToGameTest(IsolatedAsyncioTestCase):
    async def test_retries_a_timed_out_navigation(self):
        context = AsyncMock()
        stuck_page = AsyncMock()
        new_page = AsyncMock()
        stuck_page.goto.side_effect = PlaywrightTimeoutError("timed out")
        context.new_page.return_value = new_page
        prepare_page = AsyncMock()

        with patch(
            "hauntedroom.runner.navigation.asyncio.sleep", new_callable=AsyncMock
        ) as sleep:
            result = await navigate_to_game(
                context,
                stuck_page,
                "https://game.example/",
                attempts=2,
                timeout_ms=10,
                retry_delay_seconds=0,
                prepare_page=prepare_page,
            )

        self.assertIs(result, new_page)
        stuck_page.goto.assert_awaited_once_with(
            "https://game.example/", wait_until="commit", timeout=10
        )
        stuck_page.close.assert_awaited_once_with()
        context.new_page.assert_awaited_once_with()
        new_page.goto.assert_awaited_once_with(
            "https://game.example/", wait_until="commit", timeout=10
        )
        prepare_page.assert_has_awaits([call(stuck_page), call(new_page)])
        sleep.assert_awaited_once_with(0)

    async def test_raises_after_the_last_attempt(self):
        context = AsyncMock()
        first_page = AsyncMock()
        second_page = AsyncMock()
        error = PlaywrightTimeoutError("timed out")
        first_page.goto.side_effect = error
        second_page.goto.side_effect = error
        context.new_page.return_value = second_page

        with (
            patch(
                "hauntedroom.runner.navigation.asyncio.sleep", new_callable=AsyncMock
            ),
            self.assertRaises(PlaywrightTimeoutError),
        ):
            await navigate_to_game(
                context,
                first_page,
                "https://game.example/",
                attempts=2,
                timeout_ms=10,
                retry_delay_seconds=0,
            )

        first_page.goto.assert_awaited_once()
        first_page.close.assert_awaited_once_with()
        context.new_page.assert_awaited_once_with()
        second_page.goto.assert_awaited_once()
        second_page.close.assert_not_awaited()

    async def test_rejects_zero_attempts(self):
        with self.assertRaisesRegex(ValueError, "attempts must be at least 1"):
            await navigate_to_game(
                AsyncMock(), AsyncMock(), "https://game.example/", attempts=0
            )

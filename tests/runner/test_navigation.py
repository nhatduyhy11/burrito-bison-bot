import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.runner.navigation import navigate_to_game


class NavigateToGameTest(IsolatedAsyncioTestCase):
    async def test_retries_a_timed_out_navigation(self):
        page = AsyncMock()
        page.goto.side_effect = [PlaywrightTimeoutError("timed out"), None]

        with patch(
            "hauntedroom.runner.navigation.asyncio.sleep", new_callable=AsyncMock
        ) as sleep:
            await navigate_to_game(
                page,
                "https://game.example/",
                attempts=2,
                timeout_ms=10,
                retry_delay_seconds=0,
            )

        self.assertEqual(page.goto.await_count, 2)
        page.evaluate.assert_awaited_once_with("window.stop()")
        sleep.assert_awaited_once_with(0)

    async def test_raises_after_the_last_attempt(self):
        page = AsyncMock()
        error = PlaywrightTimeoutError("timed out")
        page.goto.side_effect = error

        with (
            patch(
                "hauntedroom.runner.navigation.asyncio.sleep", new_callable=AsyncMock
            ),
            self.assertRaises(PlaywrightTimeoutError),
        ):
            await navigate_to_game(
                page,
                "https://game.example/",
                attempts=2,
                timeout_ms=10,
                retry_delay_seconds=0,
            )

        self.assertEqual(page.goto.await_count, 2)
        page.evaluate.assert_awaited_once_with("window.stop()")

    async def test_rejects_zero_attempts(self):
        with self.assertRaisesRegex(ValueError, "attempts must be at least 1"):
            await navigate_to_game(AsyncMock(), "https://game.example/", attempts=0)

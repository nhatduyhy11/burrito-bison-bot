import asyncio

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


NAVIGATION_ATTEMPTS = 3
NAVIGATION_TIMEOUT_MS = 15_000
NAVIGATION_RETRY_DELAY_SECONDS = 2.0


async def navigate_to_game(
    page: Page,
    url: str,
    *,
    attempts: int = NAVIGATION_ATTEMPTS,
    timeout_ms: float = NAVIGATION_TIMEOUT_MS,
    retry_delay_seconds: float = NAVIGATION_RETRY_DELAY_SECONDS,
) -> None:
    """Navigate through transient hangs seen after quickly restarting Chrome."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    for attempt in range(1, attempts + 1):
        try:
            await page.goto(url, wait_until="commit", timeout=timeout_ms)
            return
        except PlaywrightTimeoutError:
            if attempt == attempts:
                raise

            print(
                f"Navigation attempt {attempt}/{attempts} timed out; "
                "stopping the pending request and retrying..."
            )
            try:
                await page.evaluate("window.stop()")
            except PlaywrightError:
                # A page can briefly reject commands while its failed navigation
                # is being torn down. The next goto() is still safe to attempt.
                pass
            await asyncio.sleep(retry_delay_seconds * attempt)

"""Navigate the game page with retries, inlined from the old bot's runner."""

import asyncio
import os
import sys
from typing import Awaitable, Callable, Optional

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import BrowserContext, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


ORANGE = "\033[38;5;208m"
RESET = "\033[0m"


def colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color codes when writing to an interactive terminal."""
    if os.environ.get("NO_COLOR") is not None or not sys.stdout.isatty():
        return text
    return f"{color}{text}{RESET}"


NAVIGATION_ATTEMPTS = 3
NAVIGATION_TIMEOUT_MS = 15_000
NAVIGATION_RETRY_DELAY_SECONDS = 2.0
PageInitializer = Callable[[Page], Awaitable[None]]


async def navigate_to_game(
    context: BrowserContext,
    page: Page,
    url: str,
    *,
    attempts: int = NAVIGATION_ATTEMPTS,
    timeout_ms: float = NAVIGATION_TIMEOUT_MS,
    retry_delay_seconds: float = NAVIGATION_RETRY_DELAY_SECONDS,
    prepare_page: Optional[PageInitializer] = None,
) -> Page:
    """Navigate through transient hangs seen after quickly restarting Chrome."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    if prepare_page is not None:
        await prepare_page(page)

    for attempt in range(1, attempts + 1):
        try:
            await page.goto(url, wait_until="commit", timeout=timeout_ms)
            return page
        except PlaywrightTimeoutError:
            if attempt == attempts:
                raise

            print(
                colorize(
                    f"Navigation attempt {attempt}/{attempts} timed out; "
                    "discarding the stuck page and retrying with a new page...",
                    ORANGE,
                )
            )
            # Keep at least one page alive in a persistent context. Closing its
            # last page can terminate the context (notably when a debugger is
            # attached), making the following context.new_page() impossible.
            await asyncio.sleep(retry_delay_seconds * attempt)
            replacement_page = await context.new_page()
            try:
                await page.close()
            except PlaywrightError:
                # The failed renderer can reject close while it is being torn down.
                # Stop using it regardless and continue with a fresh page.
                pass
            page = replacement_page
            if prepare_page is not None:
                await prepare_page(page)

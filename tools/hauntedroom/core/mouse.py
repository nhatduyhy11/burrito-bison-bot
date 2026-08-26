"""Reusable mouse gestures for browser automation."""

from typing import Literal, Optional

from .browser_hook import suppress_next_click_log
from .runtime import wait_for_flow_timeout


MouseButton = Literal["left", "middle", "right"]
SUPPORTED_MOUSE_BUTTONS: frozenset[MouseButton] = frozenset(
    {"left", "middle", "right"}
)


async def bot_click(
    page,
    position: tuple[int, int],
    *,
    button: Optional[MouseButton] = None,
) -> None:
    """Click without recording the bot-generated input as a user action."""
    await suppress_next_click_log(page)
    if button is None:
        await page.mouse.click(*position)
    else:
        await page.mouse.click(*position, button=button)


async def click_and_wait(
    page,
    position: tuple[int, int],
    wait_ms: int,
    stop_event=None,
    *,
    button: Optional[MouseButton] = None,
    click_count: int = 1,
) -> bool:
    """Bot-click one or more times, waiting cooperatively after each click."""
    for _ in range(max(1, click_count)):
        await bot_click(page, position, button=button)
        if not await wait_for_flow_timeout(page, wait_ms, stop_event):
            return False
    return True


async def scroll_and_wait(
    page,
    position: tuple[int, int],
    delta_y: int,
    wait_ms: int,
    stop_event=None,
) -> bool:
    """Move over a scrollable area, scroll vertically, then wait cooperatively."""
    await page.mouse.move(*position)
    await page.mouse.wheel(0, delta_y)
    return await wait_for_flow_timeout(page, wait_ms, stop_event)


async def smooth_drag(
    page,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    hold_before_move_ms: int = 0,
    steps: int = 10,
    step_delay_ms: int = 0,
    hold_before_release_ms: int = 0,
) -> None:
    """Drag between two points using a linear, timed mouse path."""
    if steps < 1:
        raise ValueError("steps must be at least 1")
    if min(hold_before_move_ms, step_delay_ms, hold_before_release_ms) < 0:
        raise ValueError("drag delays cannot be negative")

    await suppress_next_click_log(page)
    await page.mouse.move(*start)
    await page.mouse.down()
    try:
        if hold_before_move_ms:
            await page.wait_for_timeout(hold_before_move_ms)

        start_x, start_y = start
        end_x, end_y = end
        for step in range(1, steps + 1):
            progress = step / steps
            next_x = round(start_x + (end_x - start_x) * progress)
            next_y = round(start_y + (end_y - start_y) * progress)
            await page.mouse.move(next_x, next_y)
            if step_delay_ms:
                await page.wait_for_timeout(step_delay_ms)

        if hold_before_release_ms:
            await page.wait_for_timeout(hold_before_release_ms)
    finally:
        await page.mouse.up()

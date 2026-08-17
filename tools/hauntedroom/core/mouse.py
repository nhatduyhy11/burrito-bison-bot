"""Reusable mouse gestures for browser automation."""


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

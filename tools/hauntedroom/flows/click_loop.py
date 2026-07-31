import asyncio


CLICK_POSITION = (440, 500)
CLICK_INTERVAL_MS = 1000


async def run_click_loop(page, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await page.mouse.click(*CLICK_POSITION)
        if stop_event.is_set():
            break

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=CLICK_INTERVAL_MS / 1000,
            )
        except asyncio.TimeoutError:
            pass

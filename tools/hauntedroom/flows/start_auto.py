import asyncio

from hauntedroom.core.runtime import flow_checkpoint, wait_with_countdown
from hauntedroom.core.terminal import ORANGE, colorize


BETWEEN_MAPS_WAIT_MS = 2_000


async def map_was_lost(page) -> bool:
    """Placeholder for the future map-loss detector."""
    return False


async def run_start_automap_loop(
    page,
    start_actions,
    automap_flow,
    stop_event: asyncio.Event,
    action_runner,
    debug: bool = False,
    *,
    run_state: object,
) -> bool:
    """Loop start-room -> auto-map -> loss check -> two-second cooldown."""
    loop_index = 0
    win_count = 0

    def record_win() -> int:
        nonlocal win_count
        win_count += 1
        return win_count

    while await flow_checkpoint(stop_event):
        loop_index += 1
        wins_before_map = win_count
        print("\n" + "=" * 60, flush=True)
        print(f"Start-auto loop {loop_index} start.", flush=True)

        started = await action_runner(
            page,
            start_actions,
            loop_count=2,
            stop_event=stop_event,
            stop_after_success=True,
        )
        if not started:
            return False

        print(
            f"Start-auto loop {loop_index}: entry actions finished; "
            "auto-map start.",
            flush=True,
        )
        map_completed = await automap_flow(
            page,
            stop_event,
            debug=debug,
            on_win=record_win,
            run_state=run_state,
        )
        if not map_completed:
            return False

        if await map_was_lost(page):
            print("Map loss detected; stopping start-auto loop.", flush=True)
            return True

        if win_count == wins_before_map:
            pause_at_next_boss = getattr(
                stop_event,
                "pause_at_next_boss",
                None,
            )
            if pause_at_next_boss is None:
                print(
                    "Map completed without a detected win reward, but the "
                    "next-boss pause policy is unavailable.",
                    flush=True,
                )
            elif pause_at_next_boss(final_only=False):
                print(
                    colorize(
                        "Map completed without a detected win reward; treating "
                        "it as a loss and arming a one-shot pause at the first "
                        "boss of the next map.",
                        ORANGE,
                    ),
                    flush=True,
                )

        print("-" * 60, flush=True)
        waited = await wait_with_countdown(
            page,
            BETWEEN_MAPS_WAIT_MS,
            f"Start-auto loop {loop_index} cooldown",
            stop_event,
        )
        if not waited:
            return False

    return False

"""Train entry, five hero selections, then normal auto-battle."""

import asyncio
from typing import Awaitable, Callable, Optional

from hauntedroom.core.mouse import click_and_wait
from hauntedroom.core.runtime import flow_checkpoint, flow_time, wait_for_flow_timeout
from hauntedroom.core.template_detection import (
    TemplateWaitStatus,
    wait_for_template,
)
from hauntedroom.core.template_matching import (
    DEFAULT_TEMPLATE_THRESHOLD,
    TEMPLATE_SCALES,
    load_template,
)
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.train_select import TrainHeroMatcher
from hauntedroom.flows.train_common import (
    TRAIN_ENTRY_SETTLE_MS,
    TRAIN_BATTLE_LOAD_MS,
    TRAIN_START_BATTLE_TIMEOUT_MS,
    TRAIN_START_BATTLE_POLL_MS,
    TRAIN_SELECTION_ROUNDS,
    TRAIN_SELECTION_POLL_MS,
    TRAIN_SELECTION_SETTLE_MS,
    TRAIN_SELECTION_TIMEOUT_MS,
    TRAIN_START_BATTLE_TEMPLATE_PATH,
    train_is_available,
    find_train_challenge_click,
)


async def run_train_flow(
    page,
    automap_flow: Callable[..., Awaitable[bool]],
    stop_event: Optional[asyncio.Event] = None,
    debug: bool = False,
    *,
    run_state: Optional[object] = None,
) -> bool:
    """Enter an available train, select 2 cards five times, then auto-battle."""
    frame_bgr = await capture_page_bgr(page)
    if not train_is_available(frame_bgr):
        print("No train attempt is currently available; runner is idle.", flush=True)
        return False

    challenge_click = find_train_challenge_click(frame_bgr)
    if challenge_click is None:
        print(
            "Train attempt available, but the challenge button was not found; "
            "runner is idle.",
            flush=True,
        )
        return False

    print(
        f"Train attempt available; challenge button detected at "
        f"{challenge_click}; clicking.",
        flush=True,
    )
    if not await click_and_wait(
        page, challenge_click, TRAIN_ENTRY_SETTLE_MS, stop_event
    ):
        return False

    template_path = TRAIN_START_BATTLE_TEMPLATE_PATH
    wait_result = await wait_for_template(
        page,
        load_template(template_path),
        template_path.name,
        DEFAULT_TEMPLATE_THRESHOLD,
        TRAIN_START_BATTLE_TIMEOUT_MS,
        TRAIN_START_BATTLE_POLL_MS,
        stop_event,
        template_scales=TEMPLATE_SCALES,
    )
    if wait_result.status is TemplateWaitStatus.STOPPED:
        return False

    assert wait_result.match is not None
    x, y, score = wait_result.match
    print(
        f"Train start battle detected at {x},{y}, "
        f"score={score:.3f}; clicking.",
        flush=True,
    )
    if not await click_and_wait(page, (x, y), TRAIN_BATTLE_LOAD_MS, stop_event):
        return False

    matcher = TrainHeroMatcher()
    confirmed_rounds = 0
    deadline = flow_time(stop_event) + TRAIN_SELECTION_TIMEOUT_MS / 1000
    while confirmed_rounds < TRAIN_SELECTION_ROUNDS:
        if not await flow_checkpoint(stop_event):
            return False
        choice = matcher.find_choice(await capture_page_bgr(page))
        if choice is None:
            if flow_time(stop_event) >= deadline:
                raise TimeoutError(
                    "Timed out during train hero selection; "
                    f"confirmed {confirmed_rounds}/{TRAIN_SELECTION_ROUNDS}."
                )
            if not await wait_for_flow_timeout(
                page, TRAIN_SELECTION_POLL_MS, stop_event
            ):
                return False
            continue

        if choice.confirm:
            confirmed_rounds += 1
            deadline = flow_time(stop_event) + TRAIN_SELECTION_TIMEOUT_MS / 1000
            print(
                f"Train hero selection {confirmed_rounds}/"
                f"{TRAIN_SELECTION_ROUNDS}: confirming 2 cards.",
                flush=True,
            )
        elif choice.template_name is not None:
            print(
                f"Train option {choice.template_name!r} matched at "
                f"{choice.x},{choice.y}, score={choice.score:.3f}.",
                flush=True,
            )
        else:
            print(
                f"Train priority missed; choosing purple card at "
                f"{choice.x},{choice.y}.",
                flush=True,
            )
        if not await click_and_wait(
            page,
            (choice.x, choice.y),
            TRAIN_SELECTION_SETTLE_MS,
            stop_event,
        ):
            return False

    print("All 5 train selections confirmed; starting normal auto-battle.", flush=True)
    return await automap_flow(
        page,
        stop_event,
        debug=debug,
        run_state=run_state,
    )

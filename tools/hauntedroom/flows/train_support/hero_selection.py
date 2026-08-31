"""Train hero card selection phase (5 rounds of choosing 2 cards)."""

import asyncio
from typing import Optional

from hauntedroom.core.mouse import click_and_wait
from hauntedroom.core.runtime import flow_checkpoint, flow_time, wait_for_flow_timeout
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.train_select import TrainHeroMatcher
from hauntedroom.flows.train_support.common import (
    TRAIN_SELECTION_POLL_MS,
    TRAIN_SELECTION_ROUNDS,
    TRAIN_SELECTION_SETTLE_MS,
    TRAIN_SELECTION_TIMEOUT_MS,
)


async def select_train_heroes(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    rounds: int = TRAIN_SELECTION_ROUNDS,
    timeout_ms: int = TRAIN_SELECTION_TIMEOUT_MS,
    poll_ms: int = TRAIN_SELECTION_POLL_MS,
    settle_ms: int = TRAIN_SELECTION_SETTLE_MS,
    raise_on_timeout: bool = True,
    matcher: Optional[TrainHeroMatcher] = None,
) -> bool:
    """Select 2 cards per round for the specified number of selection rounds (default 5)."""
    if matcher is None:
        matcher = TrainHeroMatcher()
    confirmed_rounds = 0
    deadline = flow_time(stop_event) + timeout_ms / 1000

    while confirmed_rounds < rounds:
        if not await flow_checkpoint(stop_event):
            return False
        choice = matcher.find_choice(await capture_page_bgr(page))
        if choice is None:
            if flow_time(stop_event) >= deadline:
                if raise_on_timeout:
                    raise TimeoutError(
                        "Timed out during train hero selection; "
                        f"confirmed {confirmed_rounds}/{rounds}."
                    )
                print("Timed out during train hero selection.", flush=True)
                return False
            if not await wait_for_flow_timeout(page, poll_ms, stop_event):
                return False
            continue

        if choice.confirm:
            confirmed_rounds += 1
            deadline = flow_time(stop_event) + timeout_ms / 1000
            print(
                f"Train hero selection {confirmed_rounds}/"
                f"{rounds}: confirming 2 cards.",
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
            settle_ms,
            stop_event,
        ):
            return False

    return True

"""Train battle entry phase: availability checking, challenge click, and battle start."""

import asyncio
from typing import Optional

from hauntedroom.core.mouse import click_and_wait
from hauntedroom.core.runtime import flow_checkpoint, wait_for_flow_timeout
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
from hauntedroom.flows.train_support.common import (
    TRAIN_BATTLE_LOAD_MS,
    TRAIN_ENTRY_SETTLE_MS,
    TRAIN_START_BATTLE_POLL_MS,
    TRAIN_START_BATTLE_TEMPLATE_PATH,
    TRAIN_START_BATTLE_TIMEOUT_MS,
    find_train_challenge_click,
    train_is_available,
)


async def check_and_click_train_challenge(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    settle_ms: int = TRAIN_ENTRY_SETTLE_MS,
) -> bool:
    """Check if train is available and click the challenge button once."""
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
    return await click_and_wait(page, challenge_click, settle_ms, stop_event)


async def wait_for_train_challenge_available(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    poll_ms: int = 1000,
    settle_ms: int = TRAIN_ENTRY_SETTLE_MS,
) -> bool:
    """Poll continuously until train attempt is available and challenge button is clicked."""
    challenge_click = None
    while challenge_click is None:
        if not await flow_checkpoint(stop_event):
            return False
        frame_bgr = await capture_page_bgr(page)
        if train_is_available(frame_bgr):
            challenge_click = find_train_challenge_click(frame_bgr)
        if challenge_click is None:
            print("Train is not available or challenge button not found. Waiting...", flush=True)
            if not await wait_for_flow_timeout(page, poll_ms, stop_event):
                return False

    print(f"Train attempt available; clicking challenge button at {challenge_click}.", flush=True)
    return await click_and_wait(page, challenge_click, settle_ms, stop_event)


async def wait_and_click_start_battle(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    timeout_ms: int = TRAIN_START_BATTLE_TIMEOUT_MS,
    poll_ms: int = TRAIN_START_BATTLE_POLL_MS,
    load_ms: int = TRAIN_BATTLE_LOAD_MS,
) -> bool:
    """Wait for start battle button (Khieu chien) and click it."""
    template_path = TRAIN_START_BATTLE_TEMPLATE_PATH
    wait_result = await wait_for_template(
        page,
        load_template(template_path),
        template_path.name,
        DEFAULT_TEMPLATE_THRESHOLD,
        timeout_ms,
        poll_ms,
        stop_event,
        template_scales=TEMPLATE_SCALES,
    )
    if wait_result.status is TemplateWaitStatus.STOPPED:
        return False
    if wait_result.match is None:
        print("Timed out waiting for start battle button.", flush=True)
        return False

    x, y, score = wait_result.match
    print(
        f"Train start battle detected at {x},{y}, "
        f"score={score:.3f}; clicking.",
        flush=True,
    )
    return await click_and_wait(page, (x, y), load_ms, stop_event)

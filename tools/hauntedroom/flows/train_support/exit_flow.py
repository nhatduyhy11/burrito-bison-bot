"""Train battle pause-exit, train screen return, and composite ad-exit flows."""

import asyncio
from typing import Optional

import cv2

from hauntedroom.actions.pause_exit import click_pause_exit
from hauntedroom.core.runtime import flow_checkpoint, wait_for_flow_timeout
from hauntedroom.core.template_matching import (
    DEFAULT_TEMPLATE_THRESHOLD,
    find_template,
    load_template,
)
from hauntedroom.core.terminal import BLUE, colorize
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.train_support.common import (
    EXIT_CLICK_TEMPLATE_PATH,
    EXIT_CLICK_THRESHOLD,
    EXIT_DELAY_MS,
    EXIT_POLL_MS,
    EXIT_RETRY_TEMPLATE_REGION,
    EXIT_TIMEOUT_MS,
    TRAIN_OVERLAY_DISMISS_CLICK,
    TRAIN_SCREEN_TEMPLATE_PATH,
    TRAIN_SCREEN_TEMPLATE_SCALES,
    TrainCycleResult,
)
from hauntedroom.flows.train_support.entry import (
    wait_and_click_start_battle,
    wait_for_train_challenge_available,
)
from hauntedroom.flows.train_support.hero_selection import select_train_heroes
from hauntedroom.flows.train_support.pet_and_ad import (
    run_pet_and_ad_phase,
    wait_for_match_start,
)


def _failure_result(
    stop_event: Optional[asyncio.Event],
    *,
    retryable: bool,
) -> TrainCycleResult:
    if stop_event is not None and stop_event.is_set():
        return TrainCycleResult.STOPPED
    if retryable:
        return TrainCycleResult.RETRYABLE_FAILURE
    return TrainCycleResult.FATAL_FAILURE


async def exit_train_match(
    page,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    """Click pause button and click red Exit button to leave the train battle."""
    print("Clicking pause button and exiting match...", flush=True)
    exit_click_template = load_template(EXIT_CLICK_TEMPLATE_PATH)
    return await click_pause_exit(
        page,
        retry_template=exit_click_template,
        retry_template_name=EXIT_CLICK_TEMPLATE_PATH.name,
        retry_template_threshold=EXIT_CLICK_THRESHOLD,
        retry_template_scales=(1.0,),
        retry_template_region=EXIT_RETRY_TEMPLATE_REGION,
        timeout_ms=EXIT_TIMEOUT_MS,
        poll_ms=EXIT_POLL_MS,
        delay_ms=EXIT_DELAY_MS,
        label="Train Exit",
        stop_event=stop_event,
    )


async def wait_for_train_screen(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    dismiss_click: tuple[int, int] = TRAIN_OVERLAY_DISMISS_CLICK,
) -> bool:
    """Wait until train screen appears again, clicking overlay dismiss point if needed."""
    print("Waiting for train screen to appear again...", flush=True)
    train_screen_template = load_template(TRAIN_SCREEN_TEMPLATE_PATH)

    while True:
        if not await flow_checkpoint(stop_event):
            return False
        frame_bgr = await capture_page_bgr(page)
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        x, y, score = find_template(
            frame_gray,
            train_screen_template,
            TRAIN_SCREEN_TEMPLATE_PATH.name,
            scales=TRAIN_SCREEN_TEMPLATE_SCALES,
        )
        if score >= DEFAULT_TEMPLATE_THRESHOLD:
            print(f"Train screen appeared! score={score:.3f}", flush=True)
            return True

        print(
            f"Train screen not visible yet. Clicking {dismiss_click} to dismiss overlay and waiting 1s...",
            flush=True,
        )
        await page.mouse.click(*dismiss_click)
        if not await wait_for_flow_timeout(page, 1000, stop_event):
            return False


async def run_train_ad_exit_cycle(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    pet_and_ad: bool = True,
) -> TrainCycleResult:
    """Execute a single train ad-exit cycle:
    1. Wait for train challenge available and click it.
    2. Wait for start battle button and click it.
    3. Select 5 rounds of heroes.
    4. Wait for match start (detecting money template).
    5. If pet_and_ad: activate middle pet + summon + dismiss spin.
    6. Exit match via pause-exit.
    7. Wait for train screen to return.
    """
    # 1. Wait until train is available and challenge clicked
    if not await wait_for_train_challenge_available(page, stop_event):
        return _failure_result(stop_event, retryable=False)

    # 2. Wait for start battle button and click
    print("Waiting for start battle button...", flush=True)
    if not await wait_and_click_start_battle(page, stop_event):
        return _failure_result(stop_event, retryable=True)

    # 3. Hero Card Selection (Rounds 1-5)
    if not await select_train_heroes(page, stop_event, raise_on_timeout=False):
        return _failure_result(stop_event, retryable=True)

    # 4. Wait for match start
    if not await wait_for_match_start(page, stop_event):
        return _failure_result(stop_event, retryable=False)

    # 5. Pet and ad phase (if enabled)
    if pet_and_ad:
        if not await run_pet_and_ad_phase(page, stop_event):
            return _failure_result(stop_event, retryable=False)

    # 6. Exit match
    if not await exit_train_match(page, stop_event):
        return _failure_result(stop_event, retryable=True)

    # 7. Wait for train screen to return
    if not await wait_for_train_screen(page, stop_event):
        return _failure_result(stop_event, retryable=False)
    return TrainCycleResult.COMPLETED


async def run_train_ad_exit_loop(
    page,
    stop_event: Optional[asyncio.Event] = None,
    debug: bool = False,
    *,
    pet_and_ad: bool = True,
) -> bool:
    """Run train ad-exit flow indefinitely in a loop."""
    mode_name = "pet + spin then exit" if pet_and_ad else "immediate exit"
    print(f"Starting train ad exit flow (mode: {mode_name})...", flush=True)

    loop_count = 0
    while True:
        if not await flow_checkpoint(stop_event):
            return False

        loop_count += 1
        print("\n" + colorize(f"--- Train Ad Exit Loop #{loop_count} ({mode_name}) ---", BLUE), flush=True)

        cycle_result = await run_train_ad_exit_cycle(
            page,
            stop_event,
            pet_and_ad=pet_and_ad,
        )
        if cycle_result is TrainCycleResult.STOPPED:
            return False
        if cycle_result is TrainCycleResult.FATAL_FAILURE:
            print("Train ad exit cycle failed fatally; stopping loop.", flush=True)
            return False
        if cycle_result is TrainCycleResult.RETRYABLE_FAILURE:
            print(
                "Train ad exit cycle hit a temporary vision timeout; "
                "recovering the train screen before retry.",
                flush=True,
            )
            if not await wait_for_train_screen(page, stop_event):
                return False
            continue

        print(f"Train ad exit loop #{loop_count} completed!", flush=True)

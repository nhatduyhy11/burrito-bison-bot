"""Train battle entry phase: availability checking and yellow-button start."""

import asyncio
from typing import Optional

from hauntedroom.core.mouse import click_and_wait
from hauntedroom.core.runtime import (
    flow_checkpoint,
    flow_time,
    save_timeout_screenshot,
    wait_for_flow_timeout,
)
from hauntedroom.core.template_matching import load_template
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.hero_select import HEADER_TEMPLATE_PATH, find_battle_button
from hauntedroom.flows.train_support.common import (
    HERO_SELECT_SCREEN_POLL_MS,
    HERO_SELECT_SCREEN_TIMEOUT_MS,
    TRAIN_BOTTOM_SCAN_INTERVAL_MS,
    TRAIN_ENTRY_SETTLE_MS,
    TRAIN_START_MAX_CLICKS,
    find_train_bottom_button_click,
    train_is_available,
)


async def check_and_click_train_start(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    settle_ms: int = TRAIN_ENTRY_SETTLE_MS,
) -> bool:
    """Check if train is available and click the bottom yellow button once."""
    frame_bgr = await capture_page_bgr(page)
    if not train_is_available(frame_bgr):
        print("No train attempt is currently available; runner is idle.", flush=True)
        return False

    start_click = find_train_bottom_button_click(frame_bgr)
    if start_click is None:
        print(
            "Train attempt available, but no yellow start button was found in "
            "the bottom strip; runner is idle.",
            flush=True,
        )
        return False

    print(
        f"Train attempt available; start button detected at "
        f"{start_click}; clicking.",
        flush=True,
    )
    return await click_and_wait(page, start_click, settle_ms, stop_event)


async def wait_for_train_start_available(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    poll_ms: int = 1000,
    settle_ms: int = TRAIN_ENTRY_SETTLE_MS,
) -> bool:
    """Wait for entry UI, but stop when its yellow button has no availability badge."""
    start_click = None
    while start_click is None:
        if not await flow_checkpoint(stop_event):
            return False
        frame_bgr = await capture_page_bgr(page)
        if train_is_available(frame_bgr):
            start_click = find_train_bottom_button_click(frame_bgr)
        elif find_train_bottom_button_click(frame_bgr) is not None:
            print("No train attempt is currently available; runner is idle.", flush=True)
            return False
        if start_click is None:
            print("Train is not available or start button not found. Waiting...", flush=True)
            if not await wait_for_flow_timeout(page, poll_ms, stop_event):
                return False

    print(f"Train attempt available; clicking start button at {start_click}.", flush=True)
    return await click_and_wait(page, start_click, settle_ms, stop_event)


async def start_train_battle(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    scan_interval_ms: int = TRAIN_BOTTOM_SCAN_INTERVAL_MS,
    screen_timeout_ms: int = HERO_SELECT_SCREEN_TIMEOUT_MS,
    screen_poll_ms: int = HERO_SELECT_SCREEN_POLL_MS,
    max_start_clicks: int = TRAIN_START_MAX_CLICKS,
) -> bool:
    """Click the lobby's bottom yellow buttons until the strip clears.

    The lobby chain (reward claim, claim popup, challenge) always renders the
    current action as a yellow button in the bottom strip. Each pass waits one
    scan interval after a detection, re-scans for the live button, clicks it,
    and requires its availability badge before clicking. Unmarked buttons stop
    the flow; a click limit also stops entry if the UI never progresses. Once
    the strip clears, the hero-select phase takes over via
    wait_and_click_hero_select_battle.
    """
    start_clicks = 0
    while True:
        if not await flow_checkpoint(stop_event):
            return False
        frame_bgr = await capture_page_bgr(page)
        click_at = find_train_bottom_button_click(frame_bgr)
        if click_at is None:
            break
        if not train_is_available(frame_bgr):
            print("Train start button has no availability badge; stopping train flow.", flush=True)
            return False
        if start_clicks >= max_start_clicks:
            await save_timeout_screenshot(page, "train_start_stalled.png")
            print("Train start click limit reached; stopping train flow.", flush=True)
            return False
        if not await wait_for_flow_timeout(page, scan_interval_ms, stop_event):
            return False
        frame_bgr = await capture_page_bgr(page)
        click_at = find_train_bottom_button_click(frame_bgr)
        if click_at is None:
            break
        if not train_is_available(frame_bgr):
            print("Train start button has no availability badge; stopping train flow.", flush=True)
            return False
        print(f"Yellow start button detected at {click_at}; clicking.", flush=True)
        if not await click_and_wait(page, click_at, scan_interval_ms, stop_event):
            return False
        start_clicks += 1

    print(
        "No yellow start button left in the bottom strip; waiting for the "
        "hero select battle button...",
        flush=True,
    )
    return await wait_and_click_hero_select_battle(
        page,
        stop_event,
        screen_timeout_ms=screen_timeout_ms,
        screen_poll_ms=screen_poll_ms,
        settle_ms=scan_interval_ms,
    )


async def wait_and_click_hero_select_battle(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    screen_timeout_ms: int = HERO_SELECT_SCREEN_TIMEOUT_MS,
    screen_poll_ms: int = HERO_SELECT_SCREEN_POLL_MS,
    settle_ms: int = TRAIN_BOTTOM_SCAN_INTERVAL_MS,
) -> bool:
    """Wait for the hero-select screen, then click its yellow battle button.

    This is the hero-select phase proper on the train side: the lobby_train
    phase (bottom yellow strip) ends before this runs, and the card picker
    comes next. No lobby recovery here — the train screen has no blockers.
    Detection delegates to the shared flows.hero_select package; only the
    wait and click timing lives here.
    """
    header_template = load_template(HEADER_TEMPLATE_PATH)
    deadline = flow_time(stop_event) + screen_timeout_ms / 1000
    while True:
        if not await flow_checkpoint(stop_event):
            return False
        button = find_battle_button(
            await capture_page_bgr(page),
            header_template,
        )
        if button is not None:
            x, y = button.center
            print(
                f"Hero select screen ready; battle button at {x},{y}; "
                f"clicking.",
                flush=True,
            )
            return await click_and_wait(
                page,
                (x, y),
                settle_ms,
                stop_event,
            )
        if flow_time(stop_event) >= deadline:
            screenshot_path = await save_timeout_screenshot(
                page,
                HEADER_TEMPLATE_PATH.name,
            )
            screenshot_suffix = (
                f", screenshot={screenshot_path}" if screenshot_path else ""
            )
            raise TimeoutError(
                "Timed out waiting for the hero select battle button"
                f"{screenshot_suffix}."
            )
        if not await wait_for_flow_timeout(page, screen_poll_ms, stop_event):
            return False

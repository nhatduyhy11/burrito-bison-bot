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
from hauntedroom.flows.train_support.common import (
    HERO_SELECT_HEADER_TEMPLATE_PATH,
    HERO_SELECT_SCREEN_POLL_MS,
    HERO_SELECT_SCREEN_TIMEOUT_MS,
    TRAIN_BOTTOM_SCAN_INTERVAL_MS,
    TRAIN_ENTRY_SETTLE_MS,
    find_hero_select_battle_click,
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
    """Poll continuously until train attempt is available and the start button is clicked."""
    start_click = None
    while start_click is None:
        if not await flow_checkpoint(stop_event):
            return False
        frame_bgr = await capture_page_bgr(page)
        if train_is_available(frame_bgr):
            start_click = find_train_bottom_button_click(frame_bgr)
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
) -> bool:
    """Click bottom yellow buttons until the strip clears, then start the battle.

    The lobby chain (reward claim, claim popup, challenge) always renders the
    current action as a yellow button in the bottom strip. Each pass waits one
    scan interval after a detection, re-scans for the live button, clicks it,
    and stops scanning as soon as no yellow button is detected anymore. The
    hero-select team screen appears next and needs its own yellow battle
    button clicked before the card picker shows up, so the hand-off polls for
    that banner-gated button before returning.
    """
    while True:
        if not await flow_checkpoint(stop_event):
            return False
        click_at = find_train_bottom_button_click(await capture_page_bgr(page))
        if click_at is None:
            break
        if not await wait_for_flow_timeout(page, scan_interval_ms, stop_event):
            return False
        click_at = find_train_bottom_button_click(await capture_page_bgr(page))
        if click_at is None:
            break
        print(f"Yellow start button detected at {click_at}; clicking.", flush=True)
        if not await click_and_wait(page, click_at, scan_interval_ms, stop_event):
            return False

    print(
        "No yellow start button left in the bottom strip; waiting for the "
        "hero select battle button...",
        flush=True,
    )
    header_template = load_template(HERO_SELECT_HEADER_TEMPLATE_PATH)
    deadline = flow_time(stop_event) + screen_timeout_ms / 1000
    while True:
        if not await flow_checkpoint(stop_event):
            return False
        battle_click = find_hero_select_battle_click(
            await capture_page_bgr(page),
            header_template,
        )
        if battle_click is not None:
            print(
                f"Hero select screen ready; battle button at {battle_click}; "
                f"clicking.",
                flush=True,
            )
            return await click_and_wait(
                page,
                battle_click,
                scan_interval_ms,
                stop_event,
            )
        if flow_time(stop_event) >= deadline:
            screenshot_path = await save_timeout_screenshot(
                page,
                HERO_SELECT_HEADER_TEMPLATE_PATH.name,
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

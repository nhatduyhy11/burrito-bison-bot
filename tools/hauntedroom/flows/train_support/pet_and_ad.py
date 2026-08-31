"""Pet activation, summon loop, and level spin dismissal sub-phase for train flows."""

import asyncio
from typing import Optional

import cv2

from hauntedroom.core.mouse import click_and_wait
from hauntedroom.core.runtime import flow_checkpoint, wait_for_flow_timeout
from hauntedroom.core.template_matching import find_template, load_template
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.upgrade_action import (
    LV_SPIN_SEARCH_TOP_RATIO,
    LV_SPIN_TEMPLATE_SCALES,
    LV_SPIN_TEMPLATE_THRESHOLD,
)
from hauntedroom.flows.train_support.common import (
    LV_SPIN_TEMPLATE_PATH,
    MIDDLE_PET_CLICK,
    MONEY_SEARCH_REGION,
    MONEY_TEMPLATE_PATH,
    MONEY_TEMPLATE_SCALES,
    MONEY_TEMPLATE_THRESHOLD,
    PET_ACTIVE_TEMPLATE_PATH,
    SUMMON_PET_CLICK,
    is_pet_menu_open,
)


async def wait_for_match_start(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    poll_ms: int = 200,
) -> bool:
    """Wait for match start by detecting the money template at bottom center."""
    print("Waiting for match start (detecting money template at bottom)...", flush=True)
    money_template = load_template(MONEY_TEMPLATE_PATH)
    while True:
        if not await flow_checkpoint(stop_event):
            return False
        frame_bgr = await capture_page_bgr(page)
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        x, y, score = find_template(
            frame_gray,
            money_template,
            MONEY_TEMPLATE_PATH.name,
            scales=MONEY_TEMPLATE_SCALES,
            region=MONEY_SEARCH_REGION,
        )
        if score >= MONEY_TEMPLATE_THRESHOLD:
            print(f"Match start detected! money icon score={score:.3f} at ({x}, {y})", flush=True)
            return True
        if not await wait_for_flow_timeout(page, poll_ms, stop_event):
            return False


async def activate_middle_pet_and_summon(
    page,
    stop_event: Optional[asyncio.Event] = None,
    *,
    pet_click: tuple[int, int] = MIDDLE_PET_CLICK,
    summon_click: tuple[int, int] = SUMMON_PET_CLICK,
) -> bool:
    """Click middle pet card, wait for menu to open, then click summon button repeatedly until closed."""
    print(f"Clicking on the middle pet card at {pet_click}...", flush=True)
    if not await click_and_wait(page, pet_click, 1000, stop_event):
        return False

    pet_active_template = load_template(PET_ACTIVE_TEMPLATE_PATH)

    # Wait for pet menu to open
    print("Waiting for pet menu to open...", flush=True)
    while True:
        if not await flow_checkpoint(stop_event):
            return False
        frame_bgr = await capture_page_bgr(page)
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if is_pet_menu_open(frame_gray, pet_active_template, PET_ACTIVE_TEMPLATE_PATH.name):
            print("Pet menu opened (pet_active template detected).", flush=True)
            break
        if not await wait_for_flow_timeout(page, 200, stop_event):
            return False

    # Click first summon button repeatedly every 1s until closed
    print("Pet menu opened. Clicking first summon button every 1s until closed...", flush=True)
    while True:
        if not await flow_checkpoint(stop_event):
            return False

        print(f"Clicking first summon button at {summon_click}...", flush=True)
        await page.mouse.click(*summon_click)

        if not await wait_for_flow_timeout(page, 1000, stop_event):
            return False

        frame_bgr = await capture_page_bgr(page)
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        if not is_pet_menu_open(frame_gray, pet_active_template, PET_ACTIVE_TEMPLATE_PATH.name):
            print("Pet menu closed successfully.", flush=True)
            break

    return True


async def wait_and_dismiss_level_spin(
    page,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    """Wait for level spin to appear, then click it repeatedly to dismiss until it disappears."""
    print("Waiting for level spin to appear...", flush=True)
    lv_spin_template = load_template(LV_SPIN_TEMPLATE_PATH)

    # 1. Wait for spin to appear
    spin_appeared = False
    while not spin_appeared:
        if not await flow_checkpoint(stop_event):
            return False
        frame_bgr = await capture_page_bgr(page)
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        search_top = int(frame_gray.shape[0] * LV_SPIN_SEARCH_TOP_RATIO)
        search_frame = frame_gray[search_top:, :]
        x, y, score = find_template(
            search_frame,
            lv_spin_template,
            LV_SPIN_TEMPLATE_PATH.name,
            scales=LV_SPIN_TEMPLATE_SCALES,
        )
        if score >= LV_SPIN_TEMPLATE_THRESHOLD:
            spin_appeared = True
            print(f"Level spin appeared! score={score:.3f}", flush=True)
        else:
            if not await wait_for_flow_timeout(page, 200, stop_event):
                return False

    # 2. Click level spin to dismiss until it disappears
    print("Level spin detected; clicking until it disappears.", flush=True)
    while True:
        if not await flow_checkpoint(stop_event):
            return False
        frame_bgr = await capture_page_bgr(page)
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        search_top = int(frame_gray.shape[0] * LV_SPIN_SEARCH_TOP_RATIO)
        search_frame = frame_gray[search_top:, :]
        x, y, score = find_template(
            search_frame,
            lv_spin_template,
            LV_SPIN_TEMPLATE_PATH.name,
            scales=LV_SPIN_TEMPLATE_SCALES,
        )
        if score < LV_SPIN_TEMPLATE_THRESHOLD:
            print("Level spin disappeared.", flush=True)
            break
        y += search_top
        click_x = x
        print(f"Clicking level spin at {click_x},{y} (score={score:.3f})", flush=True)
        await page.mouse.click(click_x, y)
        if not await wait_for_flow_timeout(page, 600, stop_event):
            return False

    return True


async def run_pet_and_ad_phase(
    page,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    """Run the complete pet initialization and ad-skip/spin dismissal sub-phase."""
    if not await activate_middle_pet_and_summon(page, stop_event):
        return False
    return await wait_and_dismiss_level_spin(page, stop_event)

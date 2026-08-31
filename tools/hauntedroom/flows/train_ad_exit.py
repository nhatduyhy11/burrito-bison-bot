"""Train ad exit loop flow."""

import asyncio
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

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
    find_template,
)
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.train_select import TrainHeroMatcher
from hauntedroom.actions.pause_exit import click_pause_exit
from hauntedroom.flows.train_common import (
    train_is_available,
    find_train_challenge_click,
    TRAIN_ENTRY_SETTLE_MS,
    TRAIN_BATTLE_LOAD_MS,
    TRAIN_START_BATTLE_TIMEOUT_MS,
    TRAIN_START_BATTLE_POLL_MS,
    TRAIN_START_BATTLE_TEMPLATE_PATH,
    TRAIN_SELECTION_ROUNDS,
    TRAIN_SELECTION_POLL_MS,
    TRAIN_SELECTION_SETTLE_MS,
    TRAIN_SELECTION_TIMEOUT_MS,
)
from hauntedroom.core.terminal import BLUE, colorize



def is_pet_menu_open(
    frame_gray: np.ndarray,
    pet_active_template: np.ndarray,
    pet_active_name: str,
) -> bool:
    """Check if the pet menu is open by verifying the presence of pet_active.png template."""
    x, y, score = find_template(
        frame_gray,
        pet_active_template,
        pet_active_name,
        scales=(1.0, 0.8),
    )
    return score >= 0.70


async def run_train_ad_exit_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
    debug: bool = False,
) -> bool:
    """Run the custom train flow: select normally, click middle pet at start,
    activate first triệu hồi pet repeatedly until menu closed, skip level spins, exit and repeat indefinitely.
    """
    from hauntedroom.flows.automap_support.upgrade_action import (
        LV_SPIN_TEMPLATE_THRESHOLD,
        LV_SPIN_TEMPLATE_SCALES,
        LV_SPIN_SEARCH_TOP_RATIO,
    )

    print("Starting custom train ad exit flow...", flush=True)

    # 1. Resolve templates
    money_path = Path(__file__).resolve().parents[2] / "rooms" / "automap" / "money.png"
    money_template = load_template(money_path)

    pet_active_path = Path(__file__).resolve().parents[2] / "rooms" / "boss" / "pet_active.png"
    pet_active_template = load_template(pet_active_path)

    lv_spin_path = Path(__file__).resolve().parents[2] / "rooms" / "automap" / "lv_spin.png"
    lv_spin_template = load_template(lv_spin_path)

    exit_click_path = Path(__file__).resolve().parents[2] / "rooms" / "exit_click.png"
    exit_click_template = load_template(exit_click_path)

    a_new_1_path = (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "train_ad_exit_screen"
        / "a_new_1.png"
    )
    a_new_1_template = load_template(a_new_1_path)

    loop_count = 0
    while True:
        if not await flow_checkpoint(stop_event):
            return False

        loop_count += 1
        print("\n" + colorize(f"--- Custom Train Loop #{loop_count} ---", BLUE), flush=True)

        # 2. Wait until train is available and challenge button can be clicked
        challenge_click = None
        while challenge_click is None:
            if not await flow_checkpoint(stop_event):
                return False
            frame_bgr = await capture_page_bgr(page)
            if train_is_available(frame_bgr):
                challenge_click = find_train_challenge_click(frame_bgr)
            if challenge_click is None:
                print("Train is not available or challenge button not found. Waiting...", flush=True)
                if not await wait_for_flow_timeout(page, 1000, stop_event):
                    return False

        # 3. Enter train battle
        print(f"Train attempt available; clicking challenge button at {challenge_click}.", flush=True)
        if not await click_and_wait(page, challenge_click, TRAIN_ENTRY_SETTLE_MS, stop_event):
            return False

        # 4. Wait for Khiêu chiến button and click it
        print("Waiting for start battle button...", flush=True)
        wait_result = await wait_for_template(
            page,
            load_template(TRAIN_START_BATTLE_TEMPLATE_PATH),
            TRAIN_START_BATTLE_TEMPLATE_PATH.name,
            DEFAULT_TEMPLATE_THRESHOLD,
            TRAIN_START_BATTLE_TIMEOUT_MS,
            TRAIN_START_BATTLE_POLL_MS,
            stop_event,
            template_scales=TEMPLATE_SCALES,
        )
        if wait_result.status is TemplateWaitStatus.STOPPED:
            return False
        if wait_result.match is None:
            print("Timed out waiting for start battle button. Retrying loop...", flush=True)
            continue

        x, y, score = wait_result.match
        print(f"Start battle button detected at {x},{y}, score={score:.3f}; clicking.", flush=True)
        if not await click_and_wait(page, (x, y), TRAIN_BATTLE_LOAD_MS, stop_event):
            return False

        # 5. Hero Card Selection (Rounds 1-5)
        matcher = TrainHeroMatcher()
        confirmed_rounds = 0
        deadline = flow_time(stop_event) + TRAIN_SELECTION_TIMEOUT_MS / 1000
        selection_failed = False
        while confirmed_rounds < TRAIN_SELECTION_ROUNDS:
            if not await flow_checkpoint(stop_event):
                return False
            choice = matcher.find_choice(await capture_page_bgr(page))
            if choice is None:
                if flow_time(stop_event) >= deadline:
                    print("Timed out during train hero selection. Retrying loop...", flush=True)
                    selection_failed = True
                    break
                if not await wait_for_flow_timeout(page, TRAIN_SELECTION_POLL_MS, stop_event):
                    return False
                continue

            if choice.confirm:
                confirmed_rounds += 1
                deadline = flow_time(stop_event) + TRAIN_SELECTION_TIMEOUT_MS / 1000
                print(f"Train hero selection {confirmed_rounds}/{TRAIN_SELECTION_ROUNDS}: confirming.", flush=True)
            elif choice.template_name is not None:
                print(f"Train option {choice.template_name!r} matched at {choice.x},{choice.y}, score={choice.score:.3f}.", flush=True)
            else:
                print(f"Train priority missed; choosing purple card at {choice.x},{choice.y}.", flush=True)

            if not await click_and_wait(page, (choice.x, choice.y), TRAIN_SELECTION_SETTLE_MS, stop_event):
                return False

        if selection_failed:
            continue

        # 6. Wait for match start by detecting the money template at bottom center
        print("Waiting for match start (detecting money template at bottom)...", flush=True)
        match_started = False
        while not match_started:
            if not await flow_checkpoint(stop_event):
                return False
            frame_bgr = await capture_page_bgr(page)
            frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            x, y, score = find_template(
                frame_gray,
                money_template,
                money_path.name,
                scales=(1.0, 0.8, 0.67, 0.5),
                region=(200, 600, 440, 720),
            )
            if score >= 0.65:
                match_started = True
                print(f"Match start detected! money icon score={score:.3f} at ({x}, {y})", flush=True)
            else:
                if not await wait_for_flow_timeout(page, 200, stop_event):
                    return False

        # 7. Click on the middle pet card above that (fixed position 320, 610)
        print("Clicking on the middle pet card at (320, 610)...", flush=True)
        if not await click_and_wait(page, (320, 610), 1000, stop_event):
            return False

        # 8a. Wait for pet menu to open (meaning pet_active template is detected)
        print("Waiting for pet menu to open...", flush=True)
        while True:
            if not await flow_checkpoint(stop_event):
                return False
            frame_bgr = await capture_page_bgr(page)
            frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            if is_pet_menu_open(frame_gray, pet_active_template, pet_active_path.name):
                print("Pet menu opened (pet_active template detected).", flush=True)
                break
            if not await wait_for_flow_timeout(page, 200, stop_event):
                return False

        # 8b. Click first triệu hồi button in pet menu repeatedly every 1s until closed (food icon reappears)
        print("Pet menu opened. Clicking first triệu hồi button every 1s until food icon reappears...", flush=True)
        while True:
            if not await flow_checkpoint(stop_event):
                return False

            print("Clicking first triệu hồi button at (450, 458)...", flush=True)
            await page.mouse.click(450, 458)

            if not await wait_for_flow_timeout(page, 1000, stop_event):
                return False

            frame_bgr = await capture_page_bgr(page)
            frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

            if not is_pet_menu_open(frame_gray, pet_active_template, pet_active_path.name):
                print("Pet menu closed successfully.", flush=True)
                break

        # 9. Wait for level spin to appear
        print("Waiting for level spin to appear...", flush=True)
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
                lv_spin_path.name,
                scales=LV_SPIN_TEMPLATE_SCALES,
            )
            if score >= LV_SPIN_TEMPLATE_THRESHOLD:
                spin_appeared = True
                print(f"Level spin appeared! score={score:.3f}", flush=True)
            else:
                if not await wait_for_flow_timeout(page, 200, stop_event):
                    return False

        # 10. Click level spin to dismiss until it disappears
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
                lv_spin_path.name,
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

        # 11. Click pause button and click red 'Thoát' button
        print("Clicking pause button and exiting match...", flush=True)
        exit_success = await click_pause_exit(
            page,
            retry_template=exit_click_template,
            retry_template_name=exit_click_path.name,
            retry_template_threshold=0.70,
            retry_template_scales=(1.0,),
            retry_template_region=(120, 125, 175, 175),  # PAUSE_TRIGGER_REGION
            timeout_ms=30_000,
            poll_ms=500,
            delay_ms=200,
            label="Custom Train Exit",
            stop_event=stop_event,
        )
        if not exit_success:
            return False

        # 12. Wait until train detect template (a_new_1.png) appears again
        print("Waiting for train screen to appear again...", flush=True)
        train_screen_appeared = False
        while not train_screen_appeared:
            if not await flow_checkpoint(stop_event):
                return False
            frame_bgr = await capture_page_bgr(page)
            frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            x, y, score = find_template(
                frame_gray,
                a_new_1_template,
                a_new_1_path.name,
                scales=(1.0, 0.8, 0.67),
            )
            if score >= DEFAULT_TEMPLATE_THRESHOLD:
                train_screen_appeared = True
                print(f"Train screen appeared! score={score:.3f}", flush=True)
            else:
                print("Train screen not visible yet. Clicking (251, 633) to dismiss overlay and waiting 1s...", flush=True)
                await page.mouse.click(251, 633)
                if not await wait_for_flow_timeout(page, 1000, stop_event):
                    return False

        print(f"Custom train loop #{loop_count} completed!", flush=True)

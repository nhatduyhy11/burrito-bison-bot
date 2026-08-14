"""Break through every eligible hero until the next hero is ineligible."""

import asyncio
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.runtime import flow_checkpoint, wait_for_flow_timeout
from hauntedroom.core.vision import capture_page_bgr


# The button is inside this popup-only region. The button remains yellow after
# completion, so availability additionally requires its small red "!" mark.
# The lower "Dot Pha" tab starts below y=630 and is outside both regions.
BREAKTHROUGH_BUTTON_REGION = (270, 580, 370, 620)
BREAKTHROUGH_CLICK_POSITION = (319, 600)
BREAKTHROUGH_HUE_MIN = 15
BREAKTHROUGH_HUE_MAX = 40
BREAKTHROUGH_SATURATION_MIN = 80
BREAKTHROUGH_VALUE_MIN = 100
BREAKTHROUGH_MIN_YELLOW_PIXELS = 900
BREAKTHROUGH_MARK_REGION = (345, 575, 368, 600)
BREAKTHROUGH_MARK_HUE_MAX = 10
BREAKTHROUGH_MARK_HUE_MIN_HIGH = 170
BREAKTHROUGH_MARK_SATURATION_MIN = 120
BREAKTHROUGH_MARK_VALUE_MIN = 120
BREAKTHROUGH_MARK_MIN_RED_PIXELS = 40

HERO_ARROW_RIGHT_POSITION = (480, 233)
BREAKTHROUGH_REPEAT_DELAY_MS = 800
BREAKTHROUGH_RECHECK_DELAY_MS = 1000
HERO_CHANGE_SETTLE_MS = 2000


def find_breakthrough_available(
    frame_bgr: np.ndarray,
) -> Optional[tuple[int, int]]:
    """Return the yellow button only when its red availability mark is shown."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[:2] != (720, 640):
        return None

    left, top, right, bottom = BREAKTHROUGH_BUTTON_REGION
    hsv = cv2.cvtColor(frame_bgr[top:bottom, left:right], cv2.COLOR_BGR2HSV)
    hue, saturation, value = np.moveaxis(hsv, -1, 0)
    yellow_pixels = (
        (hue >= BREAKTHROUGH_HUE_MIN)
        & (hue <= BREAKTHROUGH_HUE_MAX)
        & (saturation >= BREAKTHROUGH_SATURATION_MIN)
        & (value >= BREAKTHROUGH_VALUE_MIN)
    )
    if int(np.count_nonzero(yellow_pixels)) < BREAKTHROUGH_MIN_YELLOW_PIXELS:
        return None

    mark_left, mark_top, mark_right, mark_bottom = BREAKTHROUGH_MARK_REGION
    mark_hsv = cv2.cvtColor(
        frame_bgr[mark_top:mark_bottom, mark_left:mark_right],
        cv2.COLOR_BGR2HSV,
    )
    mark_hue, mark_saturation, mark_value = np.moveaxis(mark_hsv, -1, 0)
    red_mark_pixels = (
        (
            (mark_hue <= BREAKTHROUGH_MARK_HUE_MAX)
            | (mark_hue >= BREAKTHROUGH_MARK_HUE_MIN_HIGH)
        )
        & (mark_saturation >= BREAKTHROUGH_MARK_SATURATION_MIN)
        & (mark_value >= BREAKTHROUGH_MARK_VALUE_MIN)
    )
    if int(np.count_nonzero(red_mark_pixels)) < BREAKTHROUGH_MARK_MIN_RED_PIXELS:
        return None
    return BREAKTHROUGH_CLICK_POSITION


async def _click(page, position: tuple[int, int]) -> None:
    await page.evaluate(
        "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
    )
    await page.mouse.click(*position)


async def run_hero_up_available_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
    breakthrough_repeat_delay_ms: int = BREAKTHROUGH_REPEAT_DELAY_MS,
    breakthrough_recheck_delay_ms: int = BREAKTHROUGH_RECHECK_DELAY_MS,
    hero_change_delay_ms: int = HERO_CHANGE_SETTLE_MS,
) -> bool:
    """Click yellow breakthroughs, advancing until the next hero has none."""
    breakthrough_count = 0
    hero_change_count = 0

    while await flow_checkpoint(stop_event):
        position = find_breakthrough_available(await capture_page_bgr(page))
        if position is None:
            hero_change_count += 1
            print(
                "No available breakthrough mark on the current hero; "
                f"moving right to hero #{hero_change_count + 1}.",
                flush=True,
            )
            await _click(page, HERO_ARROW_RIGHT_POSITION)
            print(
                "Clicked the right arrow; checking the next hero in "
                f"{hero_change_delay_ms}ms.",
                flush=True,
            )
            if not await wait_for_flow_timeout(
                page,
                hero_change_delay_ms,
                stop_event,
            ):
                print("Hero breakthrough flow stopped; runner is idle.", flush=True)
                return False

            position = find_breakthrough_available(await capture_page_bgr(page))
            if position is None:
                print(
                    "No available breakthrough mark on the next hero; "
                    f"clicked {breakthrough_count} breakthrough(s). Runner is idle.",
                    flush=True,
                )
                return True

        breakthrough_count += 1
        print(
            f"Yellow breakthrough #{breakthrough_count} at "
            f"{position[0]},{position[1]}; clicking twice with a "
            f"{breakthrough_repeat_delay_ms}ms gap.",
            flush=True,
        )
        await _click(page, position)
        if not await wait_for_flow_timeout(
            page,
            breakthrough_repeat_delay_ms,
            stop_event,
        ):
            print("Hero breakthrough flow stopped; runner is idle.", flush=True)
            return False
        await _click(page, position)
        if not await wait_for_flow_timeout(
            page,
            breakthrough_recheck_delay_ms,
            stop_event,
        ):
            print("Hero breakthrough flow stopped; runner is idle.", flush=True)
            return False

    print("Hero breakthrough flow stopped; runner is idle.", flush=True)
    return False

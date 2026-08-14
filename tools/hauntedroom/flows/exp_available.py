"""Click all visible EXP upgrade badges until none remain."""

import asyncio
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.runtime import flow_checkpoint, wait_for_flow_timeout
from hauntedroom.core.vision import capture_page_bgr


EXP_AVAILABLE_SEARCH_REGION = (128, 140, 485, 570)
EXP_AVAILABLE_HUE_MIN = 10
EXP_AVAILABLE_HUE_MAX = 40
EXP_AVAILABLE_SATURATION_MIN = 80
EXP_AVAILABLE_VALUE_MIN = 180
EXP_AVAILABLE_SLOT_X = (188, 312, 436)
EXP_AVAILABLE_SLOT_Y = (209, 353, 497)
EXP_AVAILABLE_MAX_VERTICAL_OFFSET = 45
EXP_AVAILABLE_CORE_RADIUS = 24
EXP_AVAILABLE_CORE_MIN_FILL_RATIO = 0.70
EXP_CLICK_SETTLE_MS = 800


async def _click(page, x: int, y: int) -> None:
    await page.evaluate(
        "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
    )
    await page.mouse.click(x, y)


def find_exp_available_matches(frame_bgr: np.ndarray) -> list[tuple[int, int]]:
    """Return EXP badge click points ordered top-to-bottom, left-to-right."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[:2] != (720, 640):
        return []

    left, top, right, bottom = EXP_AVAILABLE_SEARCH_REGION
    hsv = cv2.cvtColor(frame_bgr[top:bottom, left:right], cv2.COLOR_BGR2HSV)
    yellow_mask = (
        (hsv[:, :, 0] >= EXP_AVAILABLE_HUE_MIN)
        & (hsv[:, :, 0] <= EXP_AVAILABLE_HUE_MAX)
        & (hsv[:, :, 1] >= EXP_AVAILABLE_SATURATION_MIN)
        & (hsv[:, :, 2] >= EXP_AVAILABLE_VALUE_MIN)
    )

    radius = EXP_AVAILABLE_CORE_RADIUS
    yy, xx = np.ogrid[-radius : radius + 1, -radius : radius + 1]
    circular_core = (xx * xx + yy * yy) <= radius * radius

    best_score: tuple[int, float, float] | None = None
    best_offset = 0
    best_fill_ratios: list[float] = []
    for offset in range(
        -EXP_AVAILABLE_MAX_VERTICAL_OFFSET,
        EXP_AVAILABLE_MAX_VERTICAL_OFFSET + 1,
    ):
        fill_ratios: list[float] = []
        for center_y in EXP_AVAILABLE_SLOT_Y:
            for center_x in EXP_AVAILABLE_SLOT_X:
                crop_x = center_x - left
                crop_y = center_y + offset - top
                core = yellow_mask[
                    crop_y - radius : crop_y + radius + 1,
                    crop_x - radius : crop_x + radius + 1,
                ]
                if core.shape != circular_core.shape:
                    fill_ratios.append(0.0)
                    continue
                fill_ratios.append(float(core[circular_core].mean()))

        score = (
            sum(
                ratio >= EXP_AVAILABLE_CORE_MIN_FILL_RATIO
                for ratio in fill_ratios
            ),
            sum(
                max(0.0, ratio - EXP_AVAILABLE_CORE_MIN_FILL_RATIO)
                for ratio in fill_ratios
            ),
            sum(fill_ratios),
        )
        if best_score is None or score > best_score:
            best_score = score
            best_offset = offset
            best_fill_ratios = fill_ratios

    return [
        (center_x, center_y + best_offset)
        for (center_y, center_x), fill_ratio in zip(
            (
                (center_y, center_x)
                for center_y in EXP_AVAILABLE_SLOT_Y
                for center_x in EXP_AVAILABLE_SLOT_X
            ),
            best_fill_ratios,
        )
        if fill_ratio >= EXP_AVAILABLE_CORE_MIN_FILL_RATIO
    ]


async def run_exp_available_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
    delay_ms: int = EXP_CLICK_SETTLE_MS,
) -> bool:
    click_count = 0
    while await flow_checkpoint(stop_event):
        matches = find_exp_available_matches(await capture_page_bgr(page))
        if not matches:
            print(
                f"No EXP available badges detected; clicked {click_count}. "
                "Runner is idle.",
                flush=True,
            )
            return True

        x, y = matches[0]
        click_count += 1
        print(
            f"EXP available badge #{click_count} at {x},{y}; clicking first "
            f"match and checking again in {delay_ms}ms.",
            flush=True,
        )
        await _click(page, x, y)
        if not await wait_for_flow_timeout(page, delay_ms, stop_event):
            print("EXP available flow stopped; runner is idle.", flush=True)
            return False

    print("EXP available flow stopped; runner is idle.", flush=True)
    return False

"""One-shot deployment of the first low-map gear."""

from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.mouse import click_and_wait, smooth_drag
from hauntedroom.core.terminal import BLUE, colorize
from hauntedroom.core.vision import capture_page_bgr


# Coordinates are calibrated for the fixed 640x720 Playwright viewport used by
# the rest of auto-map. The click itself is derived from the detected plus, so
# a few pixels of animation in the button do not matter.
GEAR_AVAILABLE_REGION = (130, 620, 200, 700)
GEAR_PLUS_MIN_HUE = 35
GEAR_PLUS_MAX_HUE = 95
GEAR_PLUS_MIN_SATURATION = 100
GEAR_PLUS_MIN_VALUE = 100
GEAR_PLUS_MIN_AREA = 150
GEAR_PLUS_MIN_SIZE = 12
GEAR_PLUS_MAX_SIZE = 26
GEAR_BUTTON_OFFSET = (-17, 18)

GEAR_MENU_REGION = (150, 440, 490, 600)
GEAR_MENU_MIN_LOW_SATURATION_RATIO = 0.15
GEAR_MENU_MAX_CYAN_RATIO = 0.40
GEAR_ITEM_POSITION = (320, 526)
GEAR_MENU_SETTLE_MS = 1_000
GEAR_MENU_OPEN_ATTEMPTS = 3
GEAR_DROP_SETTLE_MS = 800
GEAR_DRAG_HOLD_MS = 700
GEAR_DRAG_STEPS = 12
GEAR_DRAG_STEP_DELAY_MS = 50
GEAR_DROP_HOLD_MS = 150

# The door HP strip is stable even while actors and effects move around it.
# Closing small horizontal gaps joins its striped fill into one component.
DOOR_HP_REGION = (190, 410, 315, 427)
DOOR_HP_MIN_WIDTH = 55
DOOR_HP_MIN_AREA = 200
DOOR_HP_CLOSE_KERNEL = (7, 3)
# In gear_place.png the intended center is 35px right of the HP strip's left
# edge and 45px above its top edge: (215 + 35, 415 - 45) == (250, 370).
GEAR_DROP_OFFSET_FROM_HP = (35, -45)


def _valid_color_frame(frame_bgr: np.ndarray) -> bool:
    return frame_bgr.ndim == 3 and frame_bgr.shape[2] == 3


def find_gear_button(frame_bgr: np.ndarray) -> Optional[tuple[int, int]]:
    """Return the gear button center when its large green plus is visible."""
    if not _valid_color_frame(frame_bgr):
        return None
    x1, y1, x2, y2 = GEAR_AVAILABLE_REGION
    height, width = frame_bgr.shape[:2]
    if x2 > width or y2 > height:
        return None

    hsv = cv2.cvtColor(frame_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        (GEAR_PLUS_MIN_HUE, GEAR_PLUS_MIN_SATURATION, GEAR_PLUS_MIN_VALUE),
        (GEAR_PLUS_MAX_HUE, 255, 255),
    )
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
    candidates: list[tuple[int, float, float]] = []
    for component in range(1, count):
        _x, _y, component_width, component_height, area = stats[component]
        if (
            area >= GEAR_PLUS_MIN_AREA
            and GEAR_PLUS_MIN_SIZE <= component_width <= GEAR_PLUS_MAX_SIZE
            and GEAR_PLUS_MIN_SIZE <= component_height <= GEAR_PLUS_MAX_SIZE
        ):
            center_x, center_y = centroids[component]
            candidates.append((int(area), x1 + center_x, y1 + center_y))
    if not candidates:
        return None

    _area, plus_x, plus_y = max(candidates)
    offset_x, offset_y = GEAR_BUTTON_OFFSET
    return round(plus_x + offset_x), round(plus_y + offset_y)


def gear_menu_is_open(frame_bgr: np.ndarray) -> bool:
    """Recognize the desaturated blue/metal gear panel over the lower room."""
    if not _valid_color_frame(frame_bgr):
        return False
    x1, y1, x2, y2 = GEAR_MENU_REGION
    height, width = frame_bgr.shape[:2]
    if x2 > width or y2 > height:
        return False

    hsv = cv2.cvtColor(frame_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    hue, saturation, value = np.moveaxis(hsv, -1, 0)
    low_saturation_ratio = float(np.mean((saturation < 60) & (value > 60)))
    cyan_ratio = float(
        np.mean(
            (hue >= 80)
            & (hue <= 110)
            & (saturation > 80)
            & (value > 80)
        )
    )
    return (
        low_saturation_ratio >= GEAR_MENU_MIN_LOW_SATURATION_RATIO
        and cyan_ratio <= GEAR_MENU_MAX_CYAN_RATIO
    )


def find_gear_drop_position(
    frame_bgr: np.ndarray,
) -> Optional[tuple[int, int]]:
    """Derive the gear target from the fixed door HP strip."""
    if not _valid_color_frame(frame_bgr):
        return None
    x1, y1, x2, y2 = DOOR_HP_REGION
    height, width = frame_bgr.shape[:2]
    if x2 > width or y2 > height:
        return None

    hsv = cv2.cvtColor(frame_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        (GEAR_PLUS_MIN_HUE, 80, 80),
        (GEAR_PLUS_MAX_HUE, 255, 255),
    )
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, DOOR_HP_CLOSE_KERNEL),
    )
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask)
    candidates: list[tuple[int, int, int]] = []
    for component in range(1, count):
        local_x, local_y, component_width, _component_height, area = stats[
            component
        ]
        if area >= DOOR_HP_MIN_AREA and component_width >= DOOR_HP_MIN_WIDTH:
            candidates.append((int(area), int(local_x), int(local_y)))
    if not candidates:
        return None

    _area, hp_left, hp_top = max(candidates)
    offset_x, offset_y = GEAR_DROP_OFFSET_FROM_HP
    return x1 + hp_left + offset_x, y1 + hp_top + offset_y


async def deploy_initial_gear(
    page,
    frame_bgr: np.ndarray,
) -> bool:
    """Open, drag and verify the only gear available on the low map."""
    gear_button = find_gear_button(frame_bgr)
    if gear_button is None:
        return False

    popup_frame = frame_bgr
    for attempt in range(1, GEAR_MENU_OPEN_ATTEMPTS + 1):
        print(
            f"Initial gear is available; opening menu at {gear_button[0]},"
            f"{gear_button[1]} (attempt {attempt}/{GEAR_MENU_OPEN_ATTEMPTS}).",
            flush=True,
        )
        await click_and_wait(page, gear_button, GEAR_MENU_SETTLE_MS)
        popup_frame = await capture_page_bgr(page)
        if gear_menu_is_open(popup_frame):
            break

        if attempt < GEAR_MENU_OPEN_ATTEMPTS:
            # Refresh the button position in case its animation moved between
            # clicks. Fall back to the last known center on a transient miss.
            gear_button = find_gear_button(popup_frame) or gear_button
            print("Gear menu did not open; retrying gear click.", flush=True)
    else:
        print(
            "Gear menu did not open after "
            f"{GEAR_MENU_OPEN_ATTEMPTS} attempts; aborting placement.",
            flush=True,
        )
        return False

    drop_position = find_gear_drop_position(popup_frame)
    if drop_position is None:
        print("Door HP anchor was not found; gear was not dragged.", flush=True)
        return False

    print(
        colorize(
            f"Dragging initial gear from {GEAR_ITEM_POSITION[0]},"
            f"{GEAR_ITEM_POSITION[1]} to {drop_position[0]},{drop_position[1]} "
            "using the door HP anchor.",
            BLUE,
        ),
        flush=True,
    )
    await page.evaluate(
        "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
    )
    await smooth_drag(
        page,
        GEAR_ITEM_POSITION,
        drop_position,
        # The game changes to its placement grid only after a real click-hold.
        hold_before_move_ms=GEAR_DRAG_HOLD_MS,
        steps=GEAR_DRAG_STEPS,
        step_delay_ms=GEAR_DRAG_STEP_DELAY_MS,
        hold_before_release_ms=GEAR_DROP_HOLD_MS,
    )
    await page.wait_for_timeout(GEAR_DROP_SETTLE_MS)

    result_frame = await capture_page_bgr(page)
    menu_closed = not gear_menu_is_open(result_frame)
    plus_gone = find_gear_button(result_frame) is None
    if menu_closed and plus_gone:
        print("Initial gear placed; menu closed and availability plus is gone.", flush=True)
        return True

    print(
        "Initial gear placement could not be verified "
        f"(menu_closed={menu_closed}, plus_gone={plus_gone}).",
        flush=True,
    )
    return False

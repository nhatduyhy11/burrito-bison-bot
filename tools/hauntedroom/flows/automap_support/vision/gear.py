"""Visual detectors for initial gear deployment."""

from typing import Optional

import cv2
import numpy as np

# Coordinates are calibrated for the fixed 640x720 Playwright viewport.
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
GEAR_MENU_MIN_CYAN_RATIO = 0.10
GEAR_MENU_MAX_CYAN_RATIO = 0.40
GEAR_MENU_STRIPE_REGION = (128, 468, 148, 575)
GEAR_MENU_STRIPE_MIN_HUE = 10
GEAR_MENU_STRIPE_MAX_HUE = 35
GEAR_MENU_STRIPE_MIN_SATURATION = 70
GEAR_MENU_STRIPE_MIN_VALUE = 70
GEAR_MENU_STRIPE_MIN_AREA = 100
GEAR_MENU_STRIPE_MIN_WIDTH = 12
GEAR_MENU_STRIPE_MIN_HEIGHT = 14
GEAR_MENU_STRIPE_MAX_HEIGHT = 28
GEAR_MENU_STRIPE_MIN_SLOPE = 0.25
GEAR_MENU_STRIPE_MAX_SLOPE = 0.85
GEAR_MENU_STRIPE_REQUIRED_COMPONENTS = 3

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


def _has_gear_menu_warning_stripes(frame_bgr: np.ndarray) -> bool:
    """Detect the three diagonal yellow stripes on the popup's left rail."""
    x1, y1, x2, y2 = GEAR_MENU_STRIPE_REGION
    height, width = frame_bgr.shape[:2]
    if x2 > width or y2 > height:
        return False

    hsv = cv2.cvtColor(frame_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        (
            GEAR_MENU_STRIPE_MIN_HUE,
            GEAR_MENU_STRIPE_MIN_SATURATION,
            GEAR_MENU_STRIPE_MIN_VALUE,
        ),
        (GEAR_MENU_STRIPE_MAX_HUE, 255, 255),
    )
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask)
    matching_components = 0
    for component in range(1, count):
        _x, _y, component_width, component_height, area = stats[component]
        if (
            area < GEAR_MENU_STRIPE_MIN_AREA
            or component_width < GEAR_MENU_STRIPE_MIN_WIDTH
            or not (
                GEAR_MENU_STRIPE_MIN_HEIGHT
                <= component_height
                <= GEAR_MENU_STRIPE_MAX_HEIGHT
            )
        ):
            continue

        rows, columns = np.nonzero(labels == component)
        centered_rows = rows - np.mean(rows)
        row_variance = float(np.dot(centered_rows, centered_rows))
        if row_variance == 0:
            continue
        centered_columns = columns - np.mean(columns)
        slope = float(np.dot(centered_rows, centered_columns) / row_variance)
        if GEAR_MENU_STRIPE_MIN_SLOPE <= slope <= GEAR_MENU_STRIPE_MAX_SLOPE:
            matching_components += 1

    return matching_components >= GEAR_MENU_STRIPE_REQUIRED_COMPONENTS


def gear_menu_is_open(frame_bgr: np.ndarray) -> bool:
    """Recognize the metal panel and its diagonal warning stripes."""
    if not _valid_color_frame(frame_bgr):
        return False
    if not _has_gear_menu_warning_stripes(frame_bgr):
        return False

    x1, y1, x2, y2 = GEAR_MENU_REGION
    height, width = frame_bgr.shape[:2]
    if x2 > width or y2 > height:
        return False

    hsv = cv2.cvtColor(frame_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    hue, saturation, value = np.moveaxis(hsv, -1, 0)
    low_saturation_ratio = float(np.mean((saturation < 60) & (value > 60)))
    cyan_ratio = float(
        np.mean((hue >= 80) & (hue <= 110) & (saturation > 80) & (value > 80))
    )
    return (
        low_saturation_ratio >= GEAR_MENU_MIN_LOW_SATURATION_RATIO
        and cyan_ratio >= GEAR_MENU_MIN_CYAN_RATIO
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
        local_x, local_y, component_width, _component_height, area = stats[component]
        if area >= DOOR_HP_MIN_AREA and component_width >= DOOR_HP_MIN_WIDTH:
            candidates.append((int(area), int(local_x), int(local_y)))
    if not candidates:
        return None

    _area, hp_left, hp_top = max(candidates)
    offset_x, offset_y = GEAR_DROP_OFFSET_FROM_HP
    return x1 + hp_left + offset_x, y1 + hp_top + offset_y

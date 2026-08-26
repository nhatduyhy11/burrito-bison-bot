"""Visual queries for the diamond collection flow."""

from pathlib import Path
from typing import Literal, Optional

import cv2
import numpy as np

from hauntedroom.core.template_matching import (
    TemplateMatch,
    find_template_in_region,
)


ROOMS_DIR = Path(__file__).resolve().parents[2] / "rooms"
DIAMOND_CLOSE_TEMPLATE_PATH = ROOMS_DIR / "blocker" / "lubu_close.png"
DIAMOND_REWARD_TEMPLATE_PATH = ROOMS_DIR / "misc" / "diamond_reward_available.png"

# The three collection tabs stay fixed at the bottom of the clipboard. Search
# only the small badge corner, then click the body of the corresponding tab.
DIAMOND_TAB_SPECS = (
    ((205, 625, 235, 665), (181, 655)),
    ((285, 625, 320, 665), (273, 655)),
    ((372, 625, 402, 665), (357, 655)),
)
DIAMOND_CONTENT_REGION = (145, 135, 490, 610)
DIAMOND_POPUP_REWARD_REGION = (420, 205, 480, 270)
DIAMOND_POPUP_CLOSE_REGION = (450, 130, 500, 180)

DIAMOND_REWARD_THRESHOLD = 0.90
DIAMOND_REWARD_SCALES = (0.9, 1.0, 1.1)
DIAMOND_CLOSE_THRESHOLD = 0.90
DIAMOND_CLOSE_SCALES = (0.9, 1.0, 1.1)

# Notification badges are compact red shields containing a white exclamation.
# The old research template includes 24x24 pixels of screen-specific background,
# so it is unreliable over the many card artworks on this screen. These bounds
# describe only the reusable foreground geometry instead.
MARK_RED_HUE_MAX = 8
MARK_RED_HUE_MIN_HIGH = 170
MARK_RED_SATURATION_MIN = 140
MARK_RED_VALUE_MIN = 150
MARK_WHITE_SATURATION_MAX = 80
MARK_WHITE_VALUE_MIN = 170
MARK_WIDTH_RANGE = (10, 17)
MARK_HEIGHT_RANGE = (11, 17)
MARK_AREA_RANGE = (60, 140)
MARK_MIN_WHITE_PIXELS = 15
CONTENT_MARK_BOTTOM_LEFT_PADDING = 3


def _find_notification_marks(
    frame_bgr: np.ndarray,
    region: tuple[int, int, int, int],
    click_position: Literal["center", "bottom_left"] = "center",
    bottom_left_padding: int = 0,
) -> list[tuple[int, int]]:
    """Return red/white notification centers, top-to-bottom then left-to-right."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[:2] != (720, 640):
        return []

    left, top, right, bottom = region
    crop = frame_bgr[top:bottom, left:right]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hue, saturation, value = np.moveaxis(hsv, -1, 0)
    red = (
        ((hue <= MARK_RED_HUE_MAX) | (hue >= MARK_RED_HUE_MIN_HIGH))
        & (saturation >= MARK_RED_SATURATION_MIN)
        & (value >= MARK_RED_VALUE_MIN)
    ).astype(np.uint8)

    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(red)
    matches: list[tuple[int, int]] = []
    for component in range(1, count):
        x, y, width, height, area = (
            int(value) for value in stats[component]
        )
        if not (
            MARK_WIDTH_RANGE[0] <= width <= MARK_WIDTH_RANGE[1]
            and MARK_HEIGHT_RANGE[0] <= height <= MARK_HEIGHT_RANGE[1]
            and MARK_AREA_RANGE[0] <= area <= MARK_AREA_RANGE[1]
        ):
            continue

        padding = 1
        white_crop = hsv[
            max(0, y - padding) : min(crop.shape[0], y + height + padding),
            max(0, x - padding) : min(crop.shape[1], x + width + padding),
        ]
        white_saturation = white_crop[:, :, 1]
        white_value = white_crop[:, :, 2]
        white_pixels = (
            (white_saturation <= MARK_WHITE_SATURATION_MAX)
            & (white_value >= MARK_WHITE_VALUE_MIN)
        )
        if int(np.count_nonzero(white_pixels)) < MARK_MIN_WHITE_PIXELS:
            continue

        if click_position == "bottom_left":
            # Move beyond the badge's lower-left corner so the click lands on
            # the card body instead of the small notification shield.
            click_x = left + x - bottom_left_padding
            click_y = top + y + height - 1 + bottom_left_padding
        else:
            center_x, center_y = centroids[component]
            click_x = left + round(center_x)
            click_y = top + round(center_y)
        matches.append((click_x, click_y))

    return sorted(matches, key=lambda match: (match[1], match[0]))


def find_diamond_tabs(frame_bgr: np.ndarray) -> list[tuple[int, int, int]]:
    """Return marked collection tabs from left to right."""
    matches = []
    for tab_index, (region, click_position) in enumerate(DIAMOND_TAB_SPECS):
        if _find_notification_marks(frame_bgr, region):
            matches.append((tab_index, *click_position))
    return matches


def find_diamond_content_mark(
    frame_bgr: np.ndarray,
) -> Optional[tuple[int, int]]:
    """Return a card click below-left of the first visible notification."""
    matches = _find_notification_marks(
        frame_bgr,
        DIAMOND_CONTENT_REGION,
        click_position="bottom_left",
        bottom_left_padding=CONTENT_MARK_BOTTOM_LEFT_PADDING,
    )
    return matches[0] if matches else None


def find_diamond_popup_reward(
    frame_gray: np.ndarray,
    reward_template: np.ndarray,
) -> Optional[TemplateMatch]:
    """Find the popup reward by its combined diamond and notification image."""
    if frame_gray.ndim != 2 or frame_gray.shape != (720, 640):
        return None
    return find_template_in_region(
        frame_gray,
        reward_template,
        DIAMOND_REWARD_TEMPLATE_PATH.name,
        DIAMOND_POPUP_REWARD_REGION,
        DIAMOND_REWARD_THRESHOLD,
        scales=DIAMOND_REWARD_SCALES,
    )


def find_diamond_popup_close(
    frame_gray: np.ndarray,
    close_template: np.ndarray,
) -> Optional[TemplateMatch]:
    """Find only the foreground popup close, excluding the dimmed close behind it."""
    if frame_gray.ndim != 2 or frame_gray.shape != (720, 640):
        return None
    return find_template_in_region(
        frame_gray,
        close_template,
        DIAMOND_CLOSE_TEMPLATE_PATH.name,
        DIAMOND_POPUP_CLOSE_REGION,
        DIAMOND_CLOSE_THRESHOLD,
        scales=DIAMOND_CLOSE_SCALES,
    )

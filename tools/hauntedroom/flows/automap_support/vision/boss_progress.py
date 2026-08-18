"""Visual queries for the boss progress bar."""

from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.vision import ColorComponentMatch

# The red boss icon is a stable anchor for the progress endpoint, while the
# complete top HUD can move by a few pixels between battle layouts. Restricting
# the search to its fixed neighborhood avoids other red battle effects.
BOSS_PROGRESS_ANCHOR_SEARCH_REGION = (395, 45, 435, 85)
BOSS_PROGRESS_ANCHOR_RED_MIN_SATURATION = 100
BOSS_PROGRESS_ANCHOR_RED_MIN_VALUE = 80
BOSS_PROGRESS_ANCHOR_MIN_AREA = 100
BOSS_PROGRESS_ANCHOR_MIN_WIDTH = 14
BOSS_PROGRESS_ANCHOR_MAX_WIDTH = 22
BOSS_PROGRESS_ANCHOR_MIN_HEIGHT = 14
BOSS_PROGRESS_ANCHOR_MAX_HEIGHT = 22
BOSS_PROGRESS_ANCHOR_MIN_FILL_RATIO = 0.30
BOSS_PROGRESS_ANCHOR_CLOSE_KERNEL = (3, 3)

# Offsets from the red component's top-left corner to the yellow endpoint
# immediately before the icon. Coordinates remain exclusive at x2/y2.
BOSS_PROGRESS_END_LEFT_OFFSET = -10
BOSS_PROGRESS_END_RIGHT_OFFSET = -1
BOSS_PROGRESS_END_TOP_OFFSET = 3
BOSS_PROGRESS_END_BOTTOM_OFFSET = 14

BOSS_PROGRESS_MIN_HUE = 10
BOSS_PROGRESS_MAX_HUE = 35
BOSS_PROGRESS_MIN_SATURATION = 100
BOSS_PROGRESS_MIN_VALUE = 120
BOSS_PROGRESS_MIN_YELLOW_RATIO = 0.85


def _valid_region(
    image: np.ndarray,
    region: tuple[int, int, int, int],
) -> bool:
    x1, y1, x2, y2 = region
    height, width = image.shape[:2]
    return (
        x1 >= 0
        and y1 >= 0
        and x2 <= width
        and y2 <= height
        and x1 < x2
        and y1 < y2
    )


def find_boss_progress_anchor(
    frame_bgr: np.ndarray,
    region: tuple[int, int, int, int] = BOSS_PROGRESS_ANCHOR_SEARCH_REGION,
) -> Optional[ColorComponentMatch]:
    """Locate the red boss icon component at the end of the progress bar."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return None
    if not _valid_region(frame_bgr, region):
        return None

    x1, y1, x2, y2 = region
    hsv = cv2.cvtColor(frame_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    low_red = cv2.inRange(
        hsv,
        (
            0,
            BOSS_PROGRESS_ANCHOR_RED_MIN_SATURATION,
            BOSS_PROGRESS_ANCHOR_RED_MIN_VALUE,
        ),
        (10, 255, 255),
    )
    high_red = cv2.inRange(
        hsv,
        (
            170,
            BOSS_PROGRESS_ANCHOR_RED_MIN_SATURATION,
            BOSS_PROGRESS_ANCHOR_RED_MIN_VALUE,
        ),
        (179, 255, 255),
    )
    red_mask = cv2.bitwise_or(low_red, high_red)
    red_mask = cv2.morphologyEx(
        red_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_RECT,
            BOSS_PROGRESS_ANCHOR_CLOSE_KERNEL,
        ),
    )

    component_count, _labels, stats, _centroids = (
        cv2.connectedComponentsWithStats(red_mask)
    )
    matches: list[ColorComponentMatch] = []
    for component in range(1, component_count):
        component_x = int(stats[component, cv2.CC_STAT_LEFT])
        component_y = int(stats[component, cv2.CC_STAT_TOP])
        component_width = int(stats[component, cv2.CC_STAT_WIDTH])
        component_height = int(stats[component, cv2.CC_STAT_HEIGHT])
        area = int(stats[component, cv2.CC_STAT_AREA])
        bounding_area = component_width * component_height
        if (
            area >= BOSS_PROGRESS_ANCHOR_MIN_AREA
            and BOSS_PROGRESS_ANCHOR_MIN_WIDTH
            <= component_width
            <= BOSS_PROGRESS_ANCHOR_MAX_WIDTH
            and BOSS_PROGRESS_ANCHOR_MIN_HEIGHT
            <= component_height
            <= BOSS_PROGRESS_ANCHOR_MAX_HEIGHT
            and bounding_area > 0
            and area / bounding_area
            >= BOSS_PROGRESS_ANCHOR_MIN_FILL_RATIO
        ):
            matches.append(
                ColorComponentMatch(
                    x=x1 + component_x,
                    y=y1 + component_y,
                    width=component_width,
                    height=component_height,
                    area=area,
                )
            )

    if not matches:
        return None
    return max(matches, key=lambda match: match.area)


def progress_end_region_from_anchor(
    anchor: ColorComponentMatch,
) -> tuple[int, int, int, int]:
    """Return the yellow endpoint region immediately before the boss icon."""
    return (
        anchor.x + BOSS_PROGRESS_END_LEFT_OFFSET,
        anchor.y + BOSS_PROGRESS_END_TOP_OFFSET,
        anchor.x + BOSS_PROGRESS_END_RIGHT_OFFSET,
        anchor.y + BOSS_PROGRESS_END_BOTTOM_OFFSET,
    )


def boss_progress_is_full(
    frame_bgr: np.ndarray,
    region: Optional[tuple[int, int, int, int]] = None,
) -> bool:
    """Return whether the progress endpoint anchored before the icon is yellow."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return False

    if region is None:
        anchor = find_boss_progress_anchor(frame_bgr)
        if anchor is None:
            return False
        region = progress_end_region_from_anchor(anchor)

    if not _valid_region(frame_bgr, region):
        return False

    x1, y1, x2, y2 = region
    hsv = cv2.cvtColor(frame_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    yellow = (
        (hsv[:, :, 0] >= BOSS_PROGRESS_MIN_HUE)
        & (hsv[:, :, 0] <= BOSS_PROGRESS_MAX_HUE)
        & (hsv[:, :, 1] >= BOSS_PROGRESS_MIN_SATURATION)
        & (hsv[:, :, 2] >= BOSS_PROGRESS_MIN_VALUE)
    )
    return float(np.count_nonzero(yellow)) / yellow.size >= (
        BOSS_PROGRESS_MIN_YELLOW_RATIO
    )

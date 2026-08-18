"""Visual queries for boss state and boss-action readiness."""

from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.template import find_template
from hauntedroom.core.vision import (
    ColorComponentMatch,
    ColorComponentPattern,
    find_color_component,
    region_has_color_component,
)

# Upper battlefield above the room entrance, expressed with exclusive x2/y2
# viewport coordinates. Bosses enter from the top or right, so their complete
# HP bar crosses this area before approaching the door. Keeping y2 above the
# doorway prevents the fixed door HP bar from becoming a candidate.
BOSS_HP_SEARCH_REGION = (117, 120, 522, 318)
BOSS_HP_TEMPLATE_THRESHOLD = 0.65
BOSS_HP_MIN_WIDTH = 55
BOSS_HP_MAX_WIDTH = 70
BOSS_HP_MIN_HEIGHT = 8
BOSS_HP_MAX_HEIGHT = 14
# A high whole-template score can still be produced by roughly the first
# three-quarters of the striped bar. Require matching evidence at both ends so
# only the complete, fixed-width HP signature is accepted.
BOSS_HP_EDGE_ANCHOR_WIDTH = 16
BOSS_HP_EDGE_ANCHOR_THRESHOLD = 0.60
BOSS_HP_OCCLUDED_TEMPLATE_THRESHOLD = 0.60
BOSS_HP_GEOMETRY_DARK_THRESHOLD = 70
BOSS_HP_GEOMETRY_MIN_WIDTH = 50
BOSS_HP_GEOMETRY_MAX_WIDTH = 72
BOSS_HP_GEOMETRY_MIN_HEIGHT = 10
BOSS_HP_GEOMETRY_MAX_HEIGHT = 22
BOSS_HP_GEOMETRY_MIN_AREA = 250

# The final boss is unlocked when the fixed top progress bar reaches its last
# pixels beside the boss icon. Checking only this stable endpoint is enough to
# distinguish the final-boss stage from earlier mini-boss stages.
BOSS_PROGRESS_END_REGION = (400, 61, 409, 72)
BOSS_PROGRESS_MIN_HUE = 10
BOSS_PROGRESS_MAX_HUE = 35
BOSS_PROGRESS_MIN_SATURATION = 100
BOSS_PROGRESS_MIN_VALUE = 120
BOSS_PROGRESS_MIN_YELLOW_RATIO = 0.85

# Both controls have a bright yellow/orange ready glow in fixed UI slots. The
# pet region spans the complete late-game cluster because the UI can show one
# to three pets. The pattern still requires a full-width energy bar, so empty
# slots, partially charged pets, and the artwork above each bar are ignored.
PET_READY_REGION = (250, 574, 390, 632)
SPELL_READY_REGION = (450, 542, 522, 623)
PET_READY_GLOW_PATTERN = ColorComponentPattern(
    lower_hsv=(15, 120, 180),
    upper_hsv=(40, 255, 255),
    min_area=250,
    min_width=35,
    max_width=45,
    min_height=8,
    max_height=14,
    min_fill_ratio=0.65,
)
SPELL_READY_GLOW_PATTERN = ColorComponentPattern(
    lower_hsv=(15, 120, 180),
    upper_hsv=(40, 255, 255),
    min_area=400,
)


def boss_spell_is_ready(frame_bgr: np.ndarray) -> bool:
    """Return whether the fixed boss-spell slot has its ready glow."""
    return region_has_color_component(
        frame_bgr,
        SPELL_READY_REGION,
        SPELL_READY_GLOW_PATTERN,
    )


def find_ready_boss_pet(
    frame_bgr: np.ndarray,
) -> Optional[ColorComponentMatch]:
    """Return the ready energy bar for the final-boss pet, when present."""
    return find_color_component(
        frame_bgr,
        PET_READY_REGION,
        PET_READY_GLOW_PATTERN,
    )


def find_active_pet_summon(
    frame_bgr: np.ndarray,
    active_reference_bgr: np.ndarray,
    template_name: str,
) -> Optional[tuple[int, int, float]]:
    """Locate the active summon control in an opened pet popup."""
    if (
        frame_bgr.ndim != 3
        or frame_bgr.shape[2] != 3
        or active_reference_bgr.ndim != 3
        or active_reference_bgr.shape[2] != 3
    ):
        return None
    return find_template(
        cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(active_reference_bgr, cv2.COLOR_BGR2GRAY),
        template_name,
        scales=(1.0,),
    )


def _vertical_edge_signature(image: np.ndarray) -> np.ndarray:
    """Describe narrow vertical stripes without depending on their color."""
    return cv2.convertScaleAbs(
        cv2.Sobel(image, cv2.CV_16S, 1, 0, ksize=3)
    )


def boss_progress_is_full(
    frame_bgr: np.ndarray,
    region: tuple[int, int, int, int] = BOSS_PROGRESS_END_REGION,
) -> bool:
    """Return whether the fixed endpoint of the top progress bar is yellow."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return False

    x1, y1, x2, y2 = region
    height, width = frame_bgr.shape[:2]
    if (
        x1 < 0
        or y1 < 0
        or x2 > width
        or y2 > height
        or x1 >= x2
        or y1 >= y2
    ):
        return False

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


def _has_full_width_hp_signature(
    search_signature: np.ndarray,
    template_signature: np.ndarray,
    center_x: int,
    center_y: int,
) -> bool:
    """Require the matched bar's left and right edge anchors to be present."""
    template_height, template_width = template_signature.shape
    left = center_x - template_width // 2
    top = center_y - template_height // 2
    candidate = search_signature[
        top : top + template_height,
        left : left + template_width,
    ]
    if candidate.shape != template_signature.shape:
        return False

    anchor_width = min(BOSS_HP_EDGE_ANCHOR_WIDTH, template_width // 2)
    for anchor_slice in (
        slice(0, anchor_width),
        slice(template_width - anchor_width, template_width),
    ):
        candidate_anchor = candidate[:, anchor_slice]
        template_anchor = template_signature[:, anchor_slice]
        score = float(
            cv2.matchTemplate(
                candidate_anchor,
                template_anchor,
                cv2.TM_CCOEFF_NORMED,
            )[0, 0]
        )
        if not np.isfinite(score) or score < BOSS_HP_EDGE_ANCHOR_THRESHOLD:
            return False
    return True


def _has_hp_geometry_signature(
    frame_gray: np.ndarray,
    center_x: int,
    center_y: int,
    template_width: int,
    template_height: int,
) -> bool:
    if frame_gray.ndim != 2:
        return False

    pad = 3
    left = center_x - template_width // 2
    top = center_y - template_height // 2
    height, width = frame_gray.shape
    if (
        left < 0
        or top < 0
        or left + template_width > width
        or top + template_height > height
    ):
        return False

    crop = frame_gray[
        max(0, top - pad) : min(height, top + template_height + pad),
        max(0, left - pad) : min(width, left + template_width + pad),
    ]
    if crop.size == 0:
        return False

    dark_mask = (crop < BOSS_HP_GEOMETRY_DARK_THRESHOLD).astype(np.uint8)
    dark_mask = cv2.morphologyEx(
        dark_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (5, 2)),
    )
    component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        dark_mask
    )
    for component in range(1, component_count):
        width = int(stats[component, cv2.CC_STAT_WIDTH])
        height = int(stats[component, cv2.CC_STAT_HEIGHT])
        area = int(stats[component, cv2.CC_STAT_AREA])
        if (
            BOSS_HP_GEOMETRY_MIN_WIDTH <= width <= BOSS_HP_GEOMETRY_MAX_WIDTH
            and BOSS_HP_GEOMETRY_MIN_HEIGHT <= height <= BOSS_HP_GEOMETRY_MAX_HEIGHT
            and area >= BOSS_HP_GEOMETRY_MIN_AREA
        ):
            return True
    return False


def find_boss_health_bar(
    frame_gray: np.ndarray,
    template: np.ndarray,
    region: tuple[int, int, int, int] = BOSS_HP_SEARCH_REGION,
    threshold: float = BOSS_HP_TEMPLATE_THRESHOLD,
) -> Optional[tuple[int, int, float]]:
    """Find a complete, fixed-width boss HP bar in the upper battlefield."""
    if frame_gray.ndim != 2 or template.ndim != 2:
        return None

    template_height, template_width = template.shape
    if not (
        BOSS_HP_MIN_WIDTH <= template_width <= BOSS_HP_MAX_WIDTH
        and BOSS_HP_MIN_HEIGHT <= template_height <= BOSS_HP_MAX_HEIGHT
    ):
        return None

    x1, y1, x2, y2 = region
    frame_height, frame_width = frame_gray.shape
    if (
        x1 < 0
        or y1 < 0
        or x2 > frame_width
        or y2 > frame_height
        or x1 >= x2
        or y1 >= y2
        or template_width > x2 - x1
        or template_height > y2 - y1
    ):
        return None

    template_signature = _vertical_edge_signature(template)
    if float(template_signature.std()) < 1.0:
        return None

    search_signature = _vertical_edge_signature(frame_gray[y1:y2, x1:x2])
    x, y, score = find_template(
        search_signature,
        template_signature,
        "boss_hp_bar.png",
        scales=(1.0,),
    )
    if score >= threshold and _has_full_width_hp_signature(
        search_signature,
        template_signature,
        x,
        y,
    ):
        return x1 + x, y1 + y, score

    global_x = x1 + x
    global_y = y1 + y
    if (
        score >= BOSS_HP_OCCLUDED_TEMPLATE_THRESHOLD
        and _has_hp_geometry_signature(
            frame_gray,
            global_x,
            global_y,
            template_width,
            template_height,
        )
    ):
        return global_x, global_y, score

    return None

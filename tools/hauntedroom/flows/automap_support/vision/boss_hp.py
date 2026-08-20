"""Visual queries for boss HP bars."""

from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.template_matching import find_template

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


def _vertical_edge_signature(image: np.ndarray) -> np.ndarray:
    """Describe narrow vertical stripes without depending on their color."""
    return cv2.convertScaleAbs(
        cv2.Sobel(image, cv2.CV_16S, 1, 0, ksize=3)
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

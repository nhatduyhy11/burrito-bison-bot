"""Domain-specific OpenCV detectors used by the auto-map battle flow."""

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.vision import find_template


# Upper battlefield above the room entrance, expressed with exclusive x2/y2
# viewport coordinates. Bosses enter from the top or right, so their complete
# HP bar crosses this area before approaching the door. Keeping y2 above the
# doorway prevents the fixed door HP bar from becoming a candidate.
BOSS_HP_SEARCH_REGION = (117, 120, 522, 308)
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

# Both controls have an animated electric outline, so their ready state is
# detected by the amount of connected bright yellow/orange glow in their fixed
# UI slots rather than by requiring the pixels to match a single animation
# frame. The reference crops calibrate how much glow constitutes "ready".
PET_READY_REGION = (292, 574, 346, 632)
SPELL_READY_REGION = (450, 542, 522, 623)
BOSS_READY_MIN_HUE = 15
BOSS_READY_MAX_HUE = 40
BOSS_READY_MIN_SATURATION = 120
BOSS_READY_MIN_VALUE = 180
BOSS_READY_COMPONENT_RATIO = 0.40
BOSS_READY_MIN_COMPONENT_PIXELS = 40

# The right-aligned price digit is more stable than the money icon or the
# complete price. Coordinates are in the fixed 640x720 Playwright viewport.
PROTECT_AVAILABLE_REGION = (328, 630, 348, 647)
WHITE_MAX_SATURATION = 50
WHITE_MIN_VALUE = 180
WHITE_MIN_PIXELS = 8

# A popup can contain one or two choices, and the single choice is vertically
# centered. Detect the yellow buttons instead of assuming fixed row positions.
BUILD_BUTTON_SEARCH_REGION = (380, 300, 480, 450)
BUILD_BUTTON_MIN_HUE = 15
BUILD_BUTTON_MAX_HUE = 40
BUILD_BUTTON_MIN_SATURATION = 100
BUILD_BUTTON_MIN_VALUE = 180
BUILD_BUTTON_MIN_AREA = 500
BUILD_BUTTON_MIN_WIDTH = 50
BUILD_BUTTON_MIN_HEIGHT = 15


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert a captured BGR viewport into the flow's matching format."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


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


def find_boss_health_bar(
    frame_gray: np.ndarray,
    template: np.ndarray,
    region: tuple[int, int, int, int] = BOSS_HP_SEARCH_REGION,
    threshold: float = BOSS_HP_TEMPLATE_THRESHOLD,
) -> Optional[tuple[int, int, float]]:
    """Find a complete, fixed-width boss HP bar in the upper battlefield.

    Matching the x-gradient makes red, orange, and green fills equivalent. The
    template is matched only at its native size, and both ends must match so a
    partial striped bar cannot pass on its left-side similarity alone. Boss and
    mini-boss bars with identical geometry cannot be distinguished from the HP
    pixels alone. Distinguishing them later will require a separate stage signal;
    it is intentionally outside this detector's current scope.

    A fully depleted final HP layer may render black and is intentionally not
    handled as a special case: the normal handoff happens while a filled layer
    is still visible.
    """
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
    if score < threshold or not _has_full_width_hp_signature(
        search_signature,
        template_signature,
        x,
        y,
    ):
        return None
    return x1 + x, y1 + y, score


def _largest_ready_glow_component(image: np.ndarray) -> int:
    """Return the largest connected bright yellow/orange component."""
    if image.ndim != 3 or image.shape[2] != 3 or image.size == 0:
        return 0

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    glow_mask = (
        (hsv[:, :, 0] >= BOSS_READY_MIN_HUE)
        & (hsv[:, :, 0] <= BOSS_READY_MAX_HUE)
        & (hsv[:, :, 1] >= BOSS_READY_MIN_SATURATION)
        & (hsv[:, :, 2] >= BOSS_READY_MIN_VALUE)
    ).astype(np.uint8)
    component_count, _labels, stats, _centroids = (
        cv2.connectedComponentsWithStats(glow_mask)
    )
    if component_count <= 1:
        return 0
    return int(stats[1:, cv2.CC_STAT_AREA].max())


def boss_action_has_ready_glow(
    frame_bgr: np.ndarray,
    ready_reference: np.ndarray,
    region: tuple[int, int, int, int],
) -> bool:
    """Detect a ready boss control without matching its animated glow shape."""
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

    reference_component = _largest_ready_glow_component(ready_reference)
    if reference_component < BOSS_READY_MIN_COMPONENT_PIXELS:
        return False

    live_component = _largest_ready_glow_component(frame_bgr[y1:y2, x1:x2])
    required_component = max(
        BOSS_READY_MIN_COMPONENT_PIXELS,
        int(reference_component * BOSS_READY_COMPONENT_RATIO),
    )
    return live_component >= required_component


def load_bgr_reference(path: Path) -> np.ndarray:
    """Load a color reference used by an auto-map detector."""
    reference = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if reference is None:
        raise ValueError(f"OpenCV could not read auto-map reference: {path}")
    return reference


def region_has_enough_white(
    image: np.ndarray,
    region: tuple[int, int, int, int] = PROTECT_AVAILABLE_REGION,
    min_pixels: int = WHITE_MIN_PIXELS,
) -> bool:
    """Return True only when the configured price region is visibly white."""
    x1, y1, x2, y2 = region
    height, width = image.shape[:2]
    if (
        x1 < 0
        or y1 < 0
        or x2 > width
        or y2 > height
        or x1 >= x2
        or y1 >= y2
    ):
        return False

    hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    _hue, saturation, value = np.moveaxis(hsv, -1, 0)
    white_pixels = (
        (saturation <= WHITE_MAX_SATURATION)
        & (value >= WHITE_MIN_VALUE)
    )
    return int(np.count_nonzero(white_pixels)) >= min_pixels


def find_first_available_build_option(
    image: np.ndarray,
) -> Optional[tuple[int, int]]:
    """Return the first top-to-bottom yellow button with a white price."""
    x1, y1, x2, y2 = BUILD_BUTTON_SEARCH_REGION
    height, width = image.shape[:2]
    if x2 > width or y2 > height:
        return None

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    search = hsv[y1:y2, x1:x2]
    yellow_mask = (
        (search[:, :, 0] >= BUILD_BUTTON_MIN_HUE)
        & (search[:, :, 0] <= BUILD_BUTTON_MAX_HUE)
        & (search[:, :, 1] >= BUILD_BUTTON_MIN_SATURATION)
        & (search[:, :, 2] >= BUILD_BUTTON_MIN_VALUE)
    ).astype(np.uint8)
    component_count, _labels, stats, _centroids = (
        cv2.connectedComponentsWithStats(yellow_mask)
    )

    buttons: list[tuple[int, int, int, int]] = []
    for component in range(1, component_count):
        local_x, local_y, button_width, button_height, area = stats[component]
        if (
            area < BUILD_BUTTON_MIN_AREA
            or button_width < BUILD_BUTTON_MIN_WIDTH
            or button_height < BUILD_BUTTON_MIN_HEIGHT
        ):
            continue
        buttons.append(
            (
                x1 + int(local_x),
                y1 + int(local_y),
                int(button_width),
                int(button_height),
            )
        )

    for button_x, button_y, button_width, button_height in sorted(
        buttons,
        key=lambda button: button[1],
    ):
        # Prices are in the right half; excluding the resource icon prevents
        # white pixels in that icon from making a red price look available.
        price_region = (
            button_x + button_width // 2,
            button_y,
            button_x + button_width,
            button_y + button_height,
        )
        if region_has_enough_white(image, price_region):
            return (
                button_x + button_width // 2,
                button_y + button_height // 2,
            )

    return None

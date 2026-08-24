"""Visual queries for hero level-up cards, without selection policy."""

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.template_matching import (
    find_template,
    find_template_matches,
    load_template,
)
from hauntedroom.core.vision import region_has_enough_white

HERO_LEVELUP_SEARCH_TOP = 460
HERO_LEVELUP_TEMPLATE_THRESHOLD = 0.80
HERO_NAME_TEMPLATE_THRESHOLD = 0.70
HERO_NAME_TEMPLATE_NAMES = {
    "01_dark_lubu.png",
    "02_hanuman.png",
    "09_pinocchio.png",
    "11_death.png",
    "11_underworld.png",
}
HERO_NAME_TEMPLATE_THRESHOLDS = {
    # Lu Bu's name renders slightly differently in these captures; its known
    # misses score about 0.696, while observed non-Lu-Bu frames stay below 0.56.
    "01_dark_lubu.png": 0.69,
}
HERO_OPTION_PANEL_TOP = 610
HERO_OPTION_PANEL_BOTTOM = 655
HERO_OPTION_MIN_SATURATION = 80
HERO_OPTION_MIN_VALUE = 40
HERO_OPTION_COLUMN_COVERAGE = 0.75
HERO_OPTION_MIN_WIDTH = 80
HERO_OPTION_MAX_COLUMN_GAP = 3
HERO_OPTION_COLOR_TOP = 610
HERO_OPTION_COLOR_BOTTOM = 655
HERO_OPTION_COLOR_LEFT_OFFSET = 43
HERO_OPTION_COLOR_RIGHT_OFFSET = 55
HERO_OPTION_PURPLE_HUE_MIN = 130
HERO_OPTION_PURPLE_HUE_MAX = 150
HERO_OPTION_YELLOW_HUE_MIN = 10
HERO_OPTION_YELLOW_HUE_MAX = 25
HERO_ASCEND_TEMPLATE_NAME = "00_hero_ascend.png"
HERO_ASCEND_TEMPLATE_THRESHOLD = 0.90
# 00_hero_ascend.png is the 25x23 bottom-right cyan corner of an ascend
# card. Its match center sits 47 pixels to the right of the card center.
HERO_ASCEND_MATCH_CENTER_OFFSET_X = -47

# The right-aligned hero level-up price digit is more stable than the money
# icon or complete price. Coordinates are in the fixed 640x720 viewport.
HERO_LEVELUP_PRICE_REGION = (328, 630, 348, 647)
HERO_PRICE_WHITE_MAX_SATURATION = 50
HERO_PRICE_WHITE_MIN_VALUE = 180
HERO_PRICE_WHITE_MIN_PIXELS = 8

# Legacy name kept while older callers migrate to the hero-specific name.
PROTECT_AVAILABLE_REGION = HERO_LEVELUP_PRICE_REGION

HERO_LEVELUP_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[4] / "rooms" / "automap" / "hero_levelup"
)
HERO_LEVELUP_TEMPLATE_PATHS = tuple(
    sorted(HERO_LEVELUP_TEMPLATE_DIR.glob("*.png"))
)
HeroLevelupFrame = tuple[np.ndarray, np.ndarray]
HeroOption = tuple[int, int, str]
HeroTemplateMatch = tuple[int, int, float]


def hero_levelup_price_is_available(image: np.ndarray) -> bool:
    """Return whether the fixed hero level-up price region is white."""
    return region_has_enough_white(
        image,
        HERO_LEVELUP_PRICE_REGION,
        min_pixels=HERO_PRICE_WHITE_MIN_PIXELS,
        max_saturation=HERO_PRICE_WHITE_MAX_SATURATION,
        min_value=HERO_PRICE_WHITE_MIN_VALUE,
    )


def load_hero_levelup_templates(
    template_paths: tuple[Path, ...] = HERO_LEVELUP_TEMPLATE_PATHS,
) -> dict[Path, np.ndarray]:
    """Load hero templates once for a newly constructed flow."""
    return {path: load_template(path) for path in template_paths}


def find_hero_option_centers(frame_bgr: np.ndarray) -> list[tuple[int, int]]:
    """Find visible 1/2/3-card layouts from their saturated bottom panels."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return []

    height, _width = frame_bgr.shape[:2]
    if height < HERO_OPTION_PANEL_BOTTOM:
        return []

    panel = frame_bgr[HERO_OPTION_PANEL_TOP:HERO_OPTION_PANEL_BOTTOM, :]
    hsv = cv2.cvtColor(panel, cv2.COLOR_BGR2HSV)
    saturated = (
        (hsv[:, :, 1] >= HERO_OPTION_MIN_SATURATION)
        & (hsv[:, :, 2] >= HERO_OPTION_MIN_VALUE)
    )
    active_columns = np.mean(saturated, axis=0) >= HERO_OPTION_COLUMN_COVERAGE

    # Text/effects can cut a very narrow vertical gap through an otherwise
    # solid card panel. Bridge those gaps while preserving inter-card spacing.
    inactive = ~active_columns
    gap_start: Optional[int] = None
    for x, is_inactive in enumerate(np.append(inactive, False)):
        if is_inactive and gap_start is None:
            gap_start = x
        elif not is_inactive and gap_start is not None:
            is_bounded = gap_start > 0 and x < active_columns.size
            if is_bounded and x - gap_start <= HERO_OPTION_MAX_COLUMN_GAP:
                active_columns[gap_start:x] = True
            gap_start = None

    runs: list[tuple[int, int]] = []
    run_start: Optional[int] = None
    for x, active in enumerate(np.append(active_columns, False)):
        if active and run_start is None:
            run_start = x
        elif not active and run_start is not None:
            if x - run_start >= HERO_OPTION_MIN_WIDTH:
                runs.append((run_start, x))
            run_start = None

    click_y = (HERO_OPTION_PANEL_TOP + HERO_OPTION_PANEL_BOTTOM) // 2
    return [((left + right - 1) // 2, click_y) for left, right in runs]


def _hero_option_median_hue(
    frame_bgr: np.ndarray,
    center: tuple[int, int],
) -> Optional[float]:
    """Read a card's hue from the stable solid strip on its lower-right edge."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return None

    x, _y = center
    strip = frame_bgr[
        HERO_OPTION_COLOR_TOP:HERO_OPTION_COLOR_BOTTOM,
        max(0, x + HERO_OPTION_COLOR_LEFT_OFFSET):
        min(frame_bgr.shape[1], x + HERO_OPTION_COLOR_RIGHT_OFFSET),
    ]
    if strip.size == 0:
        return None

    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    colored = (
        (hsv[:, :, 1] >= HERO_OPTION_MIN_SATURATION)
        & (hsv[:, :, 2] >= HERO_OPTION_MIN_VALUE)
    )
    hues = hsv[:, :, 0][colored]
    if hues.size == 0:
        return None
    return float(np.median(hues))


def hero_option_is_purple(
    frame_bgr: np.ndarray,
    center: tuple[int, int],
) -> bool:
    """Return whether a hero option has a purple panel."""
    median_hue = _hero_option_median_hue(frame_bgr, center)
    if median_hue is None:
        return False
    return HERO_OPTION_PURPLE_HUE_MIN <= median_hue <= HERO_OPTION_PURPLE_HUE_MAX


def hero_option_is_yellow(
    frame_bgr: np.ndarray,
    center: tuple[int, int],
) -> bool:
    """Return whether a hero option has a yellow panel."""
    median_hue = _hero_option_median_hue(frame_bgr, center)
    if median_hue is None:
        return False
    return HERO_OPTION_YELLOW_HUE_MIN <= median_hue <= HERO_OPTION_YELLOW_HUE_MAX


def hero_option_color(
    frame_bgr: np.ndarray,
    center: tuple[int, int],
) -> str:
    """Classify a detected card panel without ranking the colors."""
    if hero_option_is_yellow(frame_bgr, center):
        return "yellow"
    if hero_option_is_purple(frame_bgr, center):
        return "purple"
    return "red"


def find_hero_ascend_options(
    frame_gray: np.ndarray,
    template: np.ndarray,
    threshold: float = HERO_ASCEND_TEMPLATE_THRESHOLD,
) -> list[tuple[int, int, float]]:
    """Return all ascend-card centers found from their stable cyan corner."""
    if frame_gray.ndim != 2 or frame_gray.shape[0] <= HERO_LEVELUP_SEARCH_TOP:
        return []

    matches = find_template_matches(
        frame_gray[HERO_LEVELUP_SEARCH_TOP:, :],
        template,
        HERO_ASCEND_TEMPLATE_NAME,
        threshold=threshold,
        scales=(1.0,),
    )
    click_y = (HERO_OPTION_PANEL_TOP + HERO_OPTION_PANEL_BOTTOM) // 2
    return sorted(
        (
            (x + HERO_ASCEND_MATCH_CENTER_OFFSET_X, click_y, score)
            for x, _local_y, score in matches
        ),
        key=lambda match: match[0],
    )


def prepare_hero_levelup_frame(
    frame_bgr: np.ndarray,
) -> Optional[HeroLevelupFrame]:
    """Validate and grayscale one captured picker frame."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return None
    return frame_bgr, cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)


def find_hero_ascend_matches(
    frame: HeroLevelupFrame,
    template: np.ndarray,
    threshold: float = HERO_LEVELUP_TEMPLATE_THRESHOLD,
) -> list[HeroTemplateMatch]:
    """Answer whether the prepared frame contains ascend cards."""
    _frame_bgr, frame_gray = frame
    return find_hero_ascend_options(
        frame_gray,
        template,
        threshold=max(threshold, HERO_ASCEND_TEMPLATE_THRESHOLD),
    )


def find_hero_template_match(
    frame: HeroLevelupFrame,
    template_path: Path,
    template: np.ndarray,
    threshold: float = HERO_LEVELUP_TEMPLATE_THRESHOLD,
) -> Optional[HeroTemplateMatch]:
    """Confirm one named template requested by the action."""
    _frame_bgr, frame_gray = frame
    x, local_y, score = find_template(
        frame_gray[HERO_LEVELUP_SEARCH_TOP:, :],
        template,
        template_path.name,
        scales=(1.0,),
    )
    required_score = threshold
    if template_path.name in HERO_NAME_TEMPLATE_NAMES:
        required_score = HERO_NAME_TEMPLATE_THRESHOLDS.get(
            template_path.name,
            HERO_NAME_TEMPLATE_THRESHOLD,
        )
    if score < required_score:
        return None
    return x, HERO_LEVELUP_SEARCH_TOP + local_y, score


def find_hero_options(frame: HeroLevelupFrame) -> list[HeroOption]:
    """Return visible card centers and colors when fallback needs them."""
    frame_bgr, _frame_gray = frame
    return [
        (x, y, hero_option_color(frame_bgr, (x, y)))
        for x, y in find_hero_option_centers(frame_bgr)
    ]

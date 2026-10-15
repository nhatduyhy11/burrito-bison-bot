"""Game-level color vocabulary for clickable red and yellow buttons."""

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np

from hauntedroom.core.template_matching import Region
from hauntedroom.core.vision import (
    ColorComponentMatch,
    ColorComponentPattern,
    find_color_component,
)


ButtonColor = Literal["yellow", "red"]

# UI buttons share this palette across several screens. Red spans both ends of
# OpenCV's hue scale; each range is checked independently and the largest valid
# component is returned.
BUTTON_HSV_RANGES: dict[
    ButtonColor,
    tuple[tuple[tuple[int, int, int], tuple[int, int, int]], ...],
] = {
    "yellow": (((13, 80, 90), (42, 255, 255)),),
    "red": (
        ((0, 80, 80), (12, 255, 255)),
        ((165, 80, 80), (179, 255, 255)),
    ),
}


@dataclass(frozen=True)
class ButtonGeometry:
    """Connected-component constraints for one game button shape."""

    min_area: int
    min_width: int = 1
    max_width: Optional[int] = None
    min_height: int = 1
    max_height: Optional[int] = None
    min_fill_ratio: float = 0.0


@dataclass(frozen=True)
class ButtonPair:
    """Adjacent red cancel and yellow accept buttons from a modal popup."""

    red: ColorComponentMatch
    yellow: ColorComponentMatch


def find_colored_button(
    image: np.ndarray,
    region: Region,
    color: ButtonColor,
    geometry: ButtonGeometry,
) -> Optional[ColorComponentMatch]:
    """Return the largest game-button component matching color and geometry."""
    matches: list[ColorComponentMatch] = []
    for lower_hsv, upper_hsv in BUTTON_HSV_RANGES[color]:
        match = find_color_component(
            image,
            region,
            ColorComponentPattern(
                lower_hsv=lower_hsv,
                upper_hsv=upper_hsv,
                min_area=geometry.min_area,
                min_width=geometry.min_width,
                max_width=geometry.max_width,
                min_height=geometry.min_height,
                max_height=geometry.max_height,
                min_fill_ratio=geometry.min_fill_ratio,
            ),
        )
        if match is not None:
            matches.append(match)
    if not matches:
        return None
    return max(matches, key=lambda match: match.area)


def find_red_yellow_button_pair(
    image: np.ndarray,
    red_region: Region,
    yellow_region: Region,
    red_geometry: ButtonGeometry,
    yellow_geometry: ButtonGeometry,
    *,
    min_gap: int = 0,
    max_gap: int = 60,
    max_y_delta: int = 4,
    max_height_delta: int = 5,
) -> Optional[ButtonPair]:
    """Find the game's reusable cancel/accept popup control pair."""
    red = find_colored_button(image, red_region, "red", red_geometry)
    yellow = find_colored_button(image, yellow_region, "yellow", yellow_geometry)
    if red is None or yellow is None:
        return None

    gap = yellow.x - (red.x + red.width)
    if (
        not min_gap <= gap <= max_gap
        or abs(red.y - yellow.y) > max_y_delta
        or abs(red.height - yellow.height) > max_height_delta
    ):
        return None
    return ButtonPair(red=red, yellow=yellow)

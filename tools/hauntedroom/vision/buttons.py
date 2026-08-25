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

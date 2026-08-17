"""Generic OpenCV helpers that are not tied to Haunted Room flow rules."""

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass(frozen=True)
class ColorComponentPattern:
    """Geometry and HSV constraints for one connected color component."""

    lower_hsv: tuple[int, int, int]
    upper_hsv: tuple[int, int, int]
    min_area: int
    min_width: int = 1
    max_width: Optional[int] = None
    min_height: int = 1
    max_height: Optional[int] = None
    min_fill_ratio: float = 0.0


@dataclass(frozen=True)
class ColorComponentMatch:
    """Absolute geometry of a connected component matching a pattern."""

    x: int
    y: int
    width: int
    height: int
    area: int

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2


async def capture_page_grayscale(page) -> np.ndarray:
    screenshot = await page.screenshot(type="png", scale="css")
    encoded = np.frombuffer(screenshot, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError("OpenCV could not decode the Playwright screenshot.")
    return image


async def capture_page_bgr(page) -> np.ndarray:
    screenshot = await page.screenshot(type="png", scale="css")
    encoded = np.frombuffer(screenshot, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("OpenCV could not decode the Playwright screenshot.")
    return image


def find_color_component(
    image: np.ndarray,
    region: tuple[int, int, int, int],
    pattern: ColorComponentPattern,
) -> Optional[ColorComponentMatch]:
    """Return the largest region component matching color and shape."""
    if image.ndim != 3 or image.shape[2] != 3:
        return None

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
        return None

    hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, pattern.lower_hsv, pattern.upper_hsv)
    component_count, _labels, stats, _centroids = (
        cv2.connectedComponentsWithStats(mask)
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
            area >= pattern.min_area
            and component_width >= pattern.min_width
            and (
                pattern.max_width is None
                or component_width <= pattern.max_width
            )
            and component_height >= pattern.min_height
            and (
                pattern.max_height is None
                or component_height <= pattern.max_height
            )
            and bounding_area > 0
            and area / bounding_area >= pattern.min_fill_ratio
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


def region_has_color_component(
    image: np.ndarray,
    region: tuple[int, int, int, int],
    pattern: ColorComponentPattern,
) -> bool:
    """Return whether a region contains a component matching color and shape."""
    return find_color_component(image, region, pattern) is not None


def region_has_enough_white(
    image: np.ndarray,
    region: tuple[int, int, int, int],
    min_pixels: int,
    max_saturation: int,
    min_value: int,
) -> bool:
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
    white_pixels = (saturation <= max_saturation) & (value >= min_value)
    return int(np.count_nonzero(white_pixels)) >= min_pixels

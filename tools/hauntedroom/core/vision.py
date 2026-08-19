"""Generic OpenCV helpers that are not tied to Haunted Room flow rules."""

import base64
from dataclasses import dataclass
from typing import Optional
from weakref import WeakKeyDictionary

import cv2
import numpy as np


_CDP_CAPTURE_SESSIONS = WeakKeyDictionary()


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
    return await _capture_page(page, cv2.IMREAD_GRAYSCALE)


async def capture_page_bgr(page) -> np.ndarray:
    return await _capture_page(page, cv2.IMREAD_COLOR)


async def _capture_page(page, imread_mode: int) -> np.ndarray:
    # page.screenshot() captures the compositor surface and transiently shrinks
    # the visible renderer on headed Chrome/macOS. Capture the current view
    # through CDP instead, without Playwright's screenshot preparation or clip.
    session = await _capture_session(page)
    result = await session.send(
        "Page.captureScreenshot",
        {
            "format": "png",
            "fromSurface": False,
            "captureBeyondViewport": False,
        },
    )
    screenshot = base64.b64decode(result["data"])
    encoded = np.frombuffer(screenshot, dtype=np.uint8)
    image = cv2.imdecode(encoded, imread_mode)
    if image is None:
        raise RuntimeError("OpenCV could not decode the Playwright screenshot.")
    return _normalize_to_viewport(image, page.viewport_size)


async def _capture_session(page):
    session = _CDP_CAPTURE_SESSIONS.get(page)
    if session is None:
        session = await page.context.new_cdp_session(page)
        _CDP_CAPTURE_SESSIONS[page] = session
    return session


def _normalize_to_viewport(
    image: np.ndarray,
    viewport_size: Optional[dict[str, int]],
) -> np.ndarray:
    """Normalize a device-scale capture back to CSS viewport coordinates."""
    if viewport_size is None:
        return image

    target_width = viewport_size["width"]
    target_height = viewport_size["height"]
    image_height, image_width = image.shape[:2]
    if (image_width, image_height) == (target_width, target_height):
        return image

    interpolation = (
        cv2.INTER_AREA
        if image_width > target_width or image_height > target_height
        else cv2.INTER_LINEAR
    )
    return cv2.resize(
        image,
        (target_width, target_height),
        interpolation=interpolation,
    )


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

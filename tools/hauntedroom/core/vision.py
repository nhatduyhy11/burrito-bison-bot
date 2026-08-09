"""Generic OpenCV helpers that are not tied to Haunted Room flow rules."""

import cv2
import numpy as np


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

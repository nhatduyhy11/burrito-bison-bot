"""Visual queries for available structure build options."""

from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.vision import region_has_enough_white

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
WHITE_MAX_SATURATION = 50
WHITE_MIN_VALUE = 180
WHITE_MIN_PIXELS = 8


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
        if region_has_enough_white(
            image,
            price_region,
            min_pixels=WHITE_MIN_PIXELS,
            max_saturation=WHITE_MAX_SATURATION,
            min_value=WHITE_MIN_VALUE,
        ):
            return (
                button_x + button_width // 2,
                button_y + button_height // 2,
            )

    return None

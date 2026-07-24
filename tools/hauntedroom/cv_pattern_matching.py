from pathlib import Path

import cv2
import numpy as np


DEFAULT_TEMPLATE_THRESHOLD = 0.9
TEMPLATE_SCALES = (1.0, 0.67)


def validate_threshold(action: dict, index: int) -> None:
    threshold = float(action.get("threshold", DEFAULT_TEMPLATE_THRESHOLD))
    if not 0 < threshold <= 1:
        raise ValueError(
            f"Action #{index} threshold must be greater than 0 and at most 1."
        )


def load_template(path: Path) -> np.ndarray:
    template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise ValueError(f"OpenCV could not read template: {path}")
    return template


async def capture_page_grayscale(page) -> np.ndarray:
    screenshot = await page.screenshot(type="png", scale="css")
    encoded = np.frombuffer(screenshot, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError("OpenCV could not decode the Playwright screenshot.")
    return image


def find_template(
    screenshot: np.ndarray,
    template: np.ndarray,
    template_name: str,
    click_position: str = "center",
) -> tuple[int, int, float]:
    screenshot_height, screenshot_width = screenshot.shape
    best_match = None

    for scale in TEMPLATE_SCALES:
        if scale == 1.0:
            scaled_template = template
        else:
            scaled_template = cv2.resize(
                template,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_AREA,
            )

        template_height, template_width = scaled_template.shape
        if template_width > screenshot_width or template_height > screenshot_height:
            continue

        result = cv2.matchTemplate(
            screenshot,
            scaled_template,
            cv2.TM_CCOEFF_NORMED,
        )
        _, score, _, top_left = cv2.minMaxLoc(result)
        if best_match is None or score > best_match[0]:
            best_match = (score, top_left, template_width, template_height)

    if best_match is None:
        template_height, template_width = template.shape
        raise ValueError(
            f"Template {template_name!r} is {template_width}x{template_height}, "
            f"larger than screenshot {screenshot_width}x{screenshot_height} "
            f"at all configured scales."
        )

    score, top_left, template_width, template_height = best_match
    center_x = top_left[0] + template_width // 2
    if click_position == "top_middle":
        click_y = top_left[1] + min(1, template_height - 1)
    else:
        click_y = top_left[1] + template_height // 2
    return center_x, click_y, score

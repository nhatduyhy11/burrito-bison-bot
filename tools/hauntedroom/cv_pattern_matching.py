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


async def capture_page_bgr(page) -> np.ndarray:
    screenshot = await page.screenshot(type="png", scale="css")
    encoded = np.frombuffer(screenshot, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("OpenCV could not decode the Playwright screenshot.")
    return image


def find_template(
    screenshot: np.ndarray,
    template: np.ndarray,
    template_name: str,
    click_position: str = "center",
    scales: tuple[float, ...] = TEMPLATE_SCALES,
) -> tuple[int, int, float]:
    screenshot_height, screenshot_width = screenshot.shape
    best_match = None

    for scale in scales:
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
    if click_position == "bottom_left":
        click_x = top_left[0] + min(1, template_width - 1)
        click_y = top_left[1] + max(template_height - 2, 0)
        return click_x, click_y, score
    if click_position == "top_middle":
        click_y = top_left[1] + min(1, template_height - 1)
    else:
        click_y = top_left[1] + template_height // 2
    return center_x, click_y, score


def find_template_matches(
    screenshot: np.ndarray,
    template: np.ndarray,
    template_name: str,
    threshold: float = DEFAULT_TEMPLATE_THRESHOLD,
    scales: tuple[float, ...] = TEMPLATE_SCALES,
) -> list[tuple[int, int, float]]:
    """Return distinct template centers, ordered from bottom to top.

    Template matching produces a cluster of nearby hits for one visible icon. A
    connected component is reduced to its best-scoring point so callers see one
    match per icon instead of many nearly-identical matches.
    """
    screenshot_height, screenshot_width = screenshot.shape
    matches: list[tuple[int, int, float, int, int]] = []

    for scale in scales:
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
        hit_mask = (result >= threshold).astype(np.uint8)
        component_count, labels = cv2.connectedComponents(hit_mask)
        for component in range(1, component_count):
            ys, xs = np.where(labels == component)
            scores = result[ys, xs]
            best_index = int(np.argmax(scores))
            top_left_x = int(xs[best_index])
            top_left_y = int(ys[best_index])
            matches.append(
                (
                    top_left_x + template_width // 2,
                    top_left_y + template_height // 2,
                    float(scores[best_index]),
                    template_width,
                    template_height,
                )
            )

    # Remove duplicates caused by the same icon matching at multiple scales.
    distinct: list[tuple[int, int, float, int, int]] = []
    for candidate in sorted(matches, key=lambda match: match[2], reverse=True):
        x, y, _, width, height = candidate
        if any(
            abs(x - kept_x) <= max(width, kept_width) // 2
            and abs(y - kept_y) <= max(height, kept_height) // 2
            for kept_x, kept_y, _, kept_width, kept_height in distinct
        ):
            continue
        distinct.append(candidate)

    return [
        (x, y, score)
        for x, y, score, _, _ in sorted(
            distinct,
            key=lambda match: (match[1], match[2]),
            reverse=True,
        )
    ]

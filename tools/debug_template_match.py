import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from hauntedroom.core.template import TEMPLATE_SCALES, find_template


def parse_scales(raw: str) -> tuple[float, ...]:
    scales = tuple(float(part.strip()) for part in raw.split(",") if part.strip())
    if not scales:
        raise argparse.ArgumentTypeError("At least one scale is required.")
    if any(scale <= 0 for scale in scales):
        raise argparse.ArgumentTypeError("Scales must be positive.")
    return scales


def find_best_rect(
    screenshot: np.ndarray,
    template: np.ndarray,
    scales: tuple[float, ...],
) -> tuple[int, int, int, int, float]:
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
        if best_match is None or score > best_match[4]:
            best_match = (
                top_left[0],
                top_left[1],
                template_width,
                template_height,
                float(score),
            )

    if best_match is None:
        raise ValueError("Template is larger than screenshot at all scales.")
    return best_match


def write_annotation(
    screenshot_path: Path,
    color: np.ndarray,
    rect: tuple[int, int, int, int],
    click: tuple[int, int],
    output_dir: Path,
) -> Path:
    left, top, width, height = rect
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{screenshot_path.stem}_template_match.png"
    cv2.rectangle(
        color,
        (left, top),
        (left + width, top + height),
        (0, 0, 255),
        3,
    )
    cv2.circle(color, click, 5, (0, 255, 0), -1)
    cv2.circle(color, click, 7, (255, 255, 255), 1)
    cv2.imwrite(str(output_path), color)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print template match rectangle and click point for manual review."
    )
    parser.add_argument("screenshot", type=Path)
    parser.add_argument("template", type=Path)
    parser.add_argument(
        "--click-position",
        choices=("bottom_left", "center", "mid_left", "top_middle"),
        default="center",
    )
    parser.add_argument(
        "--scales",
        type=parse_scales,
        default=TEMPLATE_SCALES,
        help="Comma-separated scales, for example: 1.0,0.67,0.5",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="Write a red-rectangle/green-click preview under .tmp/template-match/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".tmp/template-match"),
    )
    args = parser.parse_args()

    screenshot_gray = cv2.imread(str(args.screenshot), cv2.IMREAD_GRAYSCALE)
    screenshot_color = cv2.imread(str(args.screenshot), cv2.IMREAD_COLOR)
    template = cv2.imread(str(args.template), cv2.IMREAD_GRAYSCALE)
    if screenshot_gray is None or screenshot_color is None:
        raise ValueError(f"OpenCV could not read screenshot: {args.screenshot}")
    if template is None:
        raise ValueError(f"OpenCV could not read template: {args.template}")

    click_x, click_y, score = find_template(
        screenshot_gray,
        template,
        args.template.name,
        args.click_position,
        args.scales,
    )
    left, top, width, height, _ = find_best_rect(
        screenshot_gray,
        template,
        args.scales,
    )
    result = {
        "screenshot": str(args.screenshot),
        "template": str(args.template),
        "score": round(score, 6),
        "rect": {
            "left": left,
            "top": top,
            "right": left + width,
            "bottom": top + height,
            "width": width,
            "height": height,
        },
        "click_position": args.click_position,
        "click": {"x": click_x, "y": click_y},
    }

    if args.annotate:
        output_path = write_annotation(
            args.screenshot,
            screenshot_color,
            (left, top, width, height),
            (click_x, click_y),
            args.output_dir,
        )
        result["annotation"] = str(output_path)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

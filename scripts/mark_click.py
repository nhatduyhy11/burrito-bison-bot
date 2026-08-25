"""Draw one minimal click cross-hair on a screenshot."""

import sys
from pathlib import Path

import cv2


def main() -> None:
    input_path, output_path, x_text, y_text = sys.argv[1:]
    image = cv2.imread(input_path)
    if image is None:
        raise SystemExit(f"Could not read {input_path}")
    x, y = int(x_text), int(y_text)
    cv2.line(image, (x - 6, y), (x + 6, y), (0, 0, 255), 1)
    cv2.line(image, (x, y - 6), (x, y + 6), (0, 0, 255), 1)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(output_path, image):
        raise SystemExit(f"Could not write {output_path}")


if __name__ == "__main__":
    main()

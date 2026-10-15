"""Visual primitives for the Night lobby and its challenge controls."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.template_matching import find_template, load_template


ROOM_DIR = Path(__file__).resolve().parents[2] / "rooms"
NIGHT_CROW_TEMPLATE_PATH = ROOM_DIR / "screen_detect" / "night_crow.png"
NIGHT_CHALLENGE_FLAME_PATH = ROOM_DIR / "night" / "challenge_flame.png"
NIGHT_TEMPLATE_THRESHOLD = 0.85
NIGHT_CROW_RELATIVE_REGION = (90, 0, 180, 90)
NIGHT_FLAME_REGION = (200, 600, 280, 710)


@lru_cache(maxsize=1)
def load_night_crow_template() -> np.ndarray:
    return load_template(NIGHT_CROW_TEMPLATE_PATH)


@lru_cache(maxsize=1)
def load_night_challenge_flame() -> np.ndarray:
    return load_template(NIGHT_CHALLENGE_FLAME_PATH)


def _content_relative_region(
    frame: np.ndarray,
    region: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    width = frame.shape[1]
    content_left = max((width - 405) // 2, 0)
    left, top, right, bottom = region
    return content_left + left, top, content_left + right, bottom


def night_lobby_visible(
    frame_bgr: np.ndarray,
    crow_template: Optional[np.ndarray] = None,
) -> bool:
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return False
    template = crow_template if crow_template is not None else load_night_crow_template()
    frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    _x, _y, score = find_template(
        frame_gray,
        template,
        NIGHT_CROW_TEMPLATE_PATH.name,
        scales=(1.0, 0.9, 1.1),
        region=_content_relative_region(frame_gray, NIGHT_CROW_RELATIVE_REGION),
    )
    return score >= NIGHT_TEMPLATE_THRESHOLD


def night_challenge_flame_visible(
    frame_bgr: np.ndarray,
    flame_template: Optional[np.ndarray] = None,
) -> bool:
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return False
    template = flame_template if flame_template is not None else load_night_challenge_flame()
    frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    _x, _y, score = find_template(
        frame_gray,
        template,
        NIGHT_CHALLENGE_FLAME_PATH.name,
        scales=(1.0,),
        region=NIGHT_FLAME_REGION,
    )
    return score >= NIGHT_TEMPLATE_THRESHOLD

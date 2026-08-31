"""Common constants and helper functions for train flows."""

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.vision.buttons import ButtonGeometry, find_colored_button


TRAIN_AVAILABLE_REGION = (126, 196, 222, 213)
TRAIN_AVAILABLE_MIN_TEXT_PIXELS = 30
# The train challenge button is yellow only while it can be pressed. Detect its
# live bounding box instead of trusting a fixed point from a different screen.
TRAIN_CHALLENGE_REGION = (320, 620, 480, 680)
TRAIN_CHALLENGE_GEOMETRY = ButtonGeometry(
    min_area=2_000,
    min_width=80,
    max_width=140,
    min_height=20,
    max_height=50,
)
TRAIN_ENTRY_SETTLE_MS = 2_000
TRAIN_BATTLE_LOAD_MS = 5_000
TRAIN_START_BATTLE_TIMEOUT_MS = 30_000
TRAIN_START_BATTLE_POLL_MS = 600
TRAIN_SELECTION_ROUNDS = 5
TRAIN_SELECTION_POLL_MS = 200
TRAIN_SELECTION_SETTLE_MS = 600
TRAIN_SELECTION_TIMEOUT_MS = 30_000
TRAIN_START_BATTLE_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2] / "rooms" / "start_battle.png"
)


def train_is_available(frame_bgr: np.ndarray) -> bool:
    """Read the green `Lượt vượt ải` row without OCR."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[:2] != (720, 640):
        return False
    left, top, right, bottom = TRAIN_AVAILABLE_REGION
    hsv = cv2.cvtColor(frame_bgr[top:bottom, left:right], cv2.COLOR_BGR2HSV)
    available_text = (
        (hsv[:, :, 0] >= 14)
        & (hsv[:, :, 0] <= 25)
        & (hsv[:, :, 1] >= 100)
        & (hsv[:, :, 2] >= 80)
    )
    return int(np.count_nonzero(available_text)) >= TRAIN_AVAILABLE_MIN_TEXT_PIXELS


def find_train_challenge_click(
    frame_bgr: np.ndarray,
) -> Optional[tuple[int, int]]:
    """Return the center of the live yellow train challenge button."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[:2] != (720, 640):
        return None

    button = find_colored_button(
        frame_bgr,
        TRAIN_CHALLENGE_REGION,
        "yellow",
        TRAIN_CHALLENGE_GEOMETRY,
    )
    return button.center if button is not None else None

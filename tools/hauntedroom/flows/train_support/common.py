"""Common constants and helper functions for train flows."""

from enum import Enum
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.template_matching import DEFAULT_TEMPLATE_THRESHOLD, find_template
from hauntedroom.vision.buttons import ButtonGeometry, find_colored_button


class TrainMode(str, Enum):
    """Execution mode for train flow."""

    NORMAL = "normal"
    EXIT_IMMEDIATELY = "exit_immediately"
    PET_AND_AD = "pet_and_ad"


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

# Timings
TRAIN_ENTRY_SETTLE_MS = 2_000
TRAIN_BATTLE_LOAD_MS = 5_000
TRAIN_START_BATTLE_TIMEOUT_MS = 30_000
TRAIN_START_BATTLE_POLL_MS = 600
TRAIN_SELECTION_ROUNDS = 5
TRAIN_SELECTION_POLL_MS = 200
TRAIN_SELECTION_SETTLE_MS = 600
TRAIN_SELECTION_TIMEOUT_MS = 30_000

# In-match & Pet & Spin Timings / Points / Thresholds
MONEY_SEARCH_REGION = (200, 600, 440, 720)
MONEY_TEMPLATE_THRESHOLD = 0.65
MONEY_TEMPLATE_SCALES = (1.0, 0.8, 0.67, 0.5)

MIDDLE_PET_CLICK = (320, 610)
SUMMON_PET_CLICK = (450, 458)
TRAIN_OVERLAY_DISMISS_CLICK = (251, 633)

PET_ACTIVE_THRESHOLD = 0.70
PET_ACTIVE_SCALES = (1.0, 0.8)

LV_SPIN_TEMPLATE_THRESHOLD = 0.70
LV_SPIN_TEMPLATE_SCALES = (1.0, 0.8, 0.67)
LV_SPIN_SEARCH_TOP_RATIO = 0.75

PAUSE_TRIGGER_REGION = (120, 125, 175, 175)
EXIT_RETRY_TEMPLATE_REGION = PAUSE_TRIGGER_REGION
EXIT_CLICK_THRESHOLD = 0.70
EXIT_TIMEOUT_MS = 30_000
EXIT_POLL_MS = 500
EXIT_DELAY_MS = 200

# Template paths
ROOM_TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "rooms"
TRAIN_START_BATTLE_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "start_battle.png"
MONEY_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "automap" / "money.png"
PET_ACTIVE_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "boss" / "pet_active.png"
LV_SPIN_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "automap" / "lv_spin.png"
EXIT_CLICK_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "exit_click.png"
TRAIN_SCREEN_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "train_ad_exit_screen"
    / "a_new_1.png"
)
TRAIN_SCREEN_TEMPLATE_SCALES = (1.0, 0.8, 0.67)


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


def is_pet_menu_open(
    frame_gray: np.ndarray,
    pet_active_template: np.ndarray,
    pet_active_name: str,
) -> bool:
    """Check if the pet menu is open by verifying the presence of pet_active.png template."""
    x, y, score = find_template(
        frame_gray,
        pet_active_template,
        pet_active_name,
        scales=PET_ACTIVE_SCALES,
    )
    return score >= PET_ACTIVE_THRESHOLD

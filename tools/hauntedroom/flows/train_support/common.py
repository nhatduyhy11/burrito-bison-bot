"""Common constants and helper functions for train flows."""

from enum import Enum
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.template_matching import find_template, load_template
from hauntedroom.core.vision import ColorComponentPattern, find_color_component
from hauntedroom.vision.buttons import ButtonGeometry, find_colored_button


class TrainMode(str, Enum):
    """Execution mode for train flow."""

    NORMAL = "normal"
    EXIT_IMMEDIATELY = "exit_immediately"
    PET_AND_AD = "pet_and_ad"


class TrainCycleResult(Enum):
    """Outcome of one ad-exit cycle, including whether the loop may retry."""

    COMPLETED = "completed"
    STOPPED = "stopped"
    RETRYABLE_FAILURE = "retryable_failure"
    FATAL_FAILURE = "fatal_failure"


TRAIN_AVAILABLE_BADGE_THRESHOLD = 0.55
TRAIN_START_MAX_CLICKS = 6

# Every start-train action (reward claim, claim popup, challenge) renders a
# yellow button somewhere in the bottom strip. Scan the whole strip instead of
# matching one fixed button. The value floor sits below the shared button
# palette so a button dimmed by a reward popup still matches, while the
# geometry stays tight enough to reject the hero-picker confirm button and
# screen decorations.
TRAIN_BOTTOM_BUTTON_REGION = (120, 600, 520, 690)
TRAIN_BOTTOM_BUTTON_PATTERN = ColorComponentPattern(
    lower_hsv=(13, 80, 80),
    upper_hsv=(42, 255, 255),
    min_area=2_000,
    min_width=80,
    max_width=140,
    min_height=20,
    max_height=50,
)

# Timings
TRAIN_ENTRY_SETTLE_MS = 2_000
TRAIN_BOTTOM_SCAN_INTERVAL_MS = 1_000
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
TRAIN_AVAILABLE_BADGE_PATH = ROOM_TEMPLATE_DIR / "misc" / "research_available.png"
MONEY_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "automap" / "money.png"
PET_ACTIVE_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "boss" / "pet_active.png"
LV_SPIN_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "automap" / "lv_spin.png"
EXIT_CLICK_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "exit_click.png"
# The train lobby is recognized by its broken station board ("Trạm N!") — a
# small stable anchor. A full-screen template stopped matching whenever the
# station number, hero, or reward progress differed from the capture.
TRAIN_SCREEN_ANCHOR_PATH = ROOM_TEMPLATE_DIR / "screen_detect" / "train_broken_board.png"
# Content-relative (70, 70, 210, 180) on the 405px content column centered in
# the 640px frame — the same anchor screen_detect uses for ScreenName.TRAIN.
TRAIN_SCREEN_ANCHOR_REGION = (187, 70, 327, 180)
TRAIN_SCREEN_ANCHOR_THRESHOLD = 0.85
TRAIN_SCREEN_ANCHOR_SCALES = (1.0, 0.9, 1.1, 0.67)
TRAIN_WIN_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "train_win.png"
TRAIN_WIN_TEMPLATE_THRESHOLD = 0.85
TRAIN_END_SETTLE_MS = 1_000
TRAIN_WIN_BUTTON_REGION = (200, 450, 440, 600)
TRAIN_WIN_BUTTON_GEOMETRY = ButtonGeometry(
    min_area=2_000,
    min_width=80,
    max_width=140,
    min_height=20,
    max_height=50,
)

# After the bottom strip clears, the hero-select screen (team confirm) still
# needs its yellow battle button clicked before the card picker appears. Wait
# for the locale-free top banner, then click that button. Same anchors as
# actions/hero_select_battle.py, duplicated because flows must not import
# actions. Button color/geometry go through the shared vision/buttons palette.
HERO_SELECT_HEADER_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "hero_select_battle_banner_top.png"
HERO_SELECT_HEADER_REGION = (210, 10, 430, 90)
HERO_SELECT_HEADER_THRESHOLD = 0.80
HERO_SELECT_HEADER_SCALES = (1.0,)
HERO_SELECT_BATTLE_BUTTON_REGION = (230, 650, 410, 719)
HERO_SELECT_BATTLE_BUTTON_GEOMETRY = ButtonGeometry(
    min_area=2_400,
    min_width=95,
    max_width=130,
    min_height=28,
    max_height=45,
    min_fill_ratio=0.65,
)
HERO_SELECT_SCREEN_TIMEOUT_MS = 30_000
HERO_SELECT_SCREEN_POLL_MS = 500


def train_is_available(frame_bgr: np.ndarray) -> bool:
    """Require a notification badge on the bottom challenge/claim button.

    The yellow button and attempt-row text remain visible at zero attempts.
    Reuse the shared badge, restricted to the button's upper-right corner so
    notifications on AFK, the shop, or reward items cannot enable entry.
    Reward claims (including a dimmed button behind the popup) stay actionable.
    """
    click_at = find_train_bottom_button_click(frame_bgr)
    if click_at is None:
        return False
    x, y = click_at
    _x, _y, score = find_template(
        cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY),
        load_template(TRAIN_AVAILABLE_BADGE_PATH),
        TRAIN_AVAILABLE_BADGE_PATH.name,
        scales=(1.0,),
        region=(x + 25, y - 35, x + 70, y + 5),
    )
    return score >= TRAIN_AVAILABLE_BADGE_THRESHOLD


def find_train_bottom_button_click(
    frame_bgr: np.ndarray,
) -> Optional[tuple[int, int]]:
    """Return the center of the yellow start button in the bottom strip."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[:2] != (720, 640):
        return None

    match = find_color_component(
        frame_bgr,
        TRAIN_BOTTOM_BUTTON_REGION,
        TRAIN_BOTTOM_BUTTON_PATTERN,
    )
    return match.center if match is not None else None


def find_hero_select_battle_click(
    frame_bgr: np.ndarray,
    header_template: np.ndarray,
) -> Optional[tuple[int, int]]:
    """Return the yellow battle button center on the hero-select screen.

    The button is only trusted while the locale-free top banner is visible, so
    look-alike buttons on other screens are ignored.
    """
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return None

    frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    _x, _y, score = find_template(
        frame_gray,
        header_template,
        HERO_SELECT_HEADER_TEMPLATE_PATH.name,
        scales=HERO_SELECT_HEADER_SCALES,
        region=HERO_SELECT_HEADER_REGION,
    )
    if score < HERO_SELECT_HEADER_THRESHOLD:
        return None

    button = find_colored_button(
        frame_bgr,
        HERO_SELECT_BATTLE_BUTTON_REGION,
        "yellow",
        HERO_SELECT_BATTLE_BUTTON_GEOMETRY,
    )
    return button.center if button is not None else None


def is_train_screen(
    frame_gray: np.ndarray,
    anchor_template: np.ndarray,
) -> bool:
    """Check the station-board anchor marking the train lobby."""
    _x, _y, score = find_template(
        frame_gray,
        anchor_template,
        TRAIN_SCREEN_ANCHOR_PATH.name,
        scales=TRAIN_SCREEN_ANCHOR_SCALES,
        region=TRAIN_SCREEN_ANCHOR_REGION,
    )
    return score >= TRAIN_SCREEN_ANCHOR_THRESHOLD


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

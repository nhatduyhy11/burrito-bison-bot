"""Detect the current Haunted Room screen from stable visual anchors."""

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.runtime import save_fallback_screenshot
from hauntedroom.core.template import find_template, load_template
from hauntedroom.core.terminal import GREEN, colorize
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.vision.boss_progress import (
    find_boss_progress_anchor,
)


SCREEN_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "rooms" / "screen_detect"
SCREEN_TEMPLATE_THRESHOLD = 0.85
SCREEN_TEMPLATE_SCALES = (1.0, 0.9, 1.1, 0.67)
GAME_CONTENT_WIDTH = 405


class ScreenName(str, Enum):
    HOME = "home"
    RESEARCH = "research"
    ARTIFACT = "artifact"
    EXP_HERO = "exp_hero"
    HERO_AVAILABLE = "hero_avail"
    TRAIN = "train"
    AUTOMAP = "automap"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScreenTemplateSpec:
    screen: ScreenName
    filename: str
    # Coordinates are relative to the left edge of the 405px game content.
    region: tuple[int, int, int, int]


SCREEN_TEMPLATE_SPECS = (
    ScreenTemplateSpec(ScreenName.HOME, "home_diamond.png", (40, 0, 125, 80)),
    ScreenTemplateSpec(
        ScreenName.RESEARCH,
        "research_spider.png",
        (0, 0, 110, 90),
    ),
    ScreenTemplateSpec(
        ScreenName.ARTIFACT,
        "artifact_robot_head.png",
        (0, 65, 125, 200),
    ),
    ScreenTemplateSpec(
        ScreenName.EXP_HERO,
        "exp_bear_head.png",
        (0, 50, 125, 155),
    ),
    ScreenTemplateSpec(
        ScreenName.HERO_AVAILABLE,
        "hero_left_arrow.png",
        (0, 175, 110, 290),
    ),
    ScreenTemplateSpec(
        ScreenName.TRAIN,
        "train_broken_board.png",
        (70, 70, 210, 180),
    ),
)


@lru_cache(maxsize=1)
def _load_screen_templates() -> tuple[tuple[ScreenTemplateSpec, np.ndarray], ...]:
    return tuple(
        (spec, load_template(SCREEN_TEMPLATE_DIR / spec.filename))
        for spec in SCREEN_TEMPLATE_SPECS
    )


def _absolute_search_region(
    frame: np.ndarray,
    relative_region: tuple[int, int, int, int],
) -> Optional[tuple[int, int, int, int]]:
    """Translate a game-relative anchor region into screenshot coordinates."""
    height, width = frame.shape[:2]
    content_left = max((width - GAME_CONTENT_WIDTH) // 2, 0)
    left, top, right, bottom = relative_region
    absolute = (
        min(content_left + left, width),
        min(top, height),
        min(content_left + right, width),
        min(bottom, height),
    )
    x1, y1, x2, y2 = absolute
    return absolute if x1 < x2 and y1 < y2 else None


def detect_screen(frame_bgr: np.ndarray) -> ScreenName:
    """Return the screen whose unique anchor best matches the current frame."""
    if frame_bgr.size == 0 or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return ScreenName.UNKNOWN

    # Auto-map already owns a robust color/geometry detector for this icon.
    if find_boss_progress_anchor(frame_bgr) is not None:
        return ScreenName.AUTOMAP

    frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    best_screen = ScreenName.UNKNOWN
    best_score = SCREEN_TEMPLATE_THRESHOLD

    for spec, template in _load_screen_templates():
        region = _absolute_search_region(frame_gray, spec.region)
        if region is None:
            continue
        try:
            _x, _y, score = find_template(
                frame_gray,
                template,
                spec.filename,
                scales=SCREEN_TEMPLATE_SCALES,
                region=region,
            )
        except ValueError:
            # A tiny or partially loaded frame cannot contain this anchor.
            continue
        if score >= best_score:
            best_screen = spec.screen
            best_score = score

    return best_screen


async def detect_current_screen(page) -> ScreenName:
    """Capture once, detect once, and log the result."""
    frame = await capture_page_bgr(page)
    screen = detect_screen(frame)
    print(
        colorize(f"[screen_detect] screen={screen.value}", GREEN),
        flush=True,
    )
    if screen is ScreenName.UNKNOWN:
        await save_fallback_screenshot(page, label="screen-detect-unknown")
    return screen

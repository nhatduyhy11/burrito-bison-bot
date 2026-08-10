"""Prioritized template matching and safe fallback for hero level-up cards."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.template import (
    find_template,
    find_template_matches,
    load_template,
)


HERO_LEVELUP_SEARCH_TOP = 460
HERO_LEVELUP_TEMPLATE_THRESHOLD = 0.80
HERO_NAME_TEMPLATE_THRESHOLD = 0.70
HERO_NAME_TEMPLATE_PRIORITIES = (1.0, 2.0, 9.0, 11.0)
HERO_IGNORED_PRIORITY = 99.0
HERO_OPTION_PANEL_TOP = 610
HERO_OPTION_PANEL_BOTTOM = 655
HERO_OPTION_MIN_SATURATION = 80
HERO_OPTION_MIN_VALUE = 40
HERO_OPTION_COLUMN_COVERAGE = 0.75
HERO_OPTION_MIN_WIDTH = 80
HERO_OPTION_MAX_COLUMN_GAP = 3
HERO_OPTION_COLOR_TOP = 610
HERO_OPTION_COLOR_BOTTOM = 655
HERO_OPTION_COLOR_LEFT_OFFSET = 43
HERO_OPTION_COLOR_RIGHT_OFFSET = 55
HERO_OPTION_PURPLE_HUE_MIN = 130
HERO_OPTION_PURPLE_HUE_MAX = 150
HERO_ASCEND_TEMPLATE_NAME = "00_hero_ascend.png"
HERO_ASCEND_TEMPLATE_THRESHOLD = 0.90
# 00_hero_ascend.png is the 25x23 bottom-right cyan corner of an ascend
# card. Its match center sits 47 pixels to the right of the card center.
HERO_ASCEND_MATCH_CENTER_OFFSET_X = -47

HERO_LEVELUP_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[3] / "rooms" / "automap" / "hero_levelup"
)


def _template_priority(path: Path) -> tuple[float, str]:
    """Sort leading numeric priorities naturally, then by filename."""
    prefix = path.stem.split("_", 1)[0]
    try:
        priority = float(prefix)
    except ValueError:
        priority = float("inf")
    return priority, path.name


HERO_LEVELUP_TEMPLATE_PATHS = tuple(
    sorted(
        HERO_LEVELUP_TEMPLATE_DIR.glob("*.png"),
        key=_template_priority,
    )
)


@dataclass(frozen=True)
class HeroLevelupChoice:
    x: int
    y: int
    template_name: Optional[str] = None
    score: Optional[float] = None
    priority: Optional[float] = None
    # TEMP FALLBACK TRACKING: remove this field together with the temporary
    # screenshot branch in AutomapFlow.hero_levelup after fallback is verified.
    fallback_color: Optional[str] = None
    fallback_option_count: Optional[int] = None

    @property
    def is_prioritized(self) -> bool:
        return self.template_name is not None


def find_hero_option_centers(frame_bgr: np.ndarray) -> list[tuple[int, int]]:
    """Find visible 1/2/3-card layouts from their saturated bottom panels."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return []

    height, width = frame_bgr.shape[:2]
    if height < HERO_OPTION_PANEL_BOTTOM:
        return []

    panel = frame_bgr[HERO_OPTION_PANEL_TOP:HERO_OPTION_PANEL_BOTTOM, :]
    hsv = cv2.cvtColor(panel, cv2.COLOR_BGR2HSV)
    saturated = (
        (hsv[:, :, 1] >= HERO_OPTION_MIN_SATURATION)
        & (hsv[:, :, 2] >= HERO_OPTION_MIN_VALUE)
    )
    active_columns = (
        np.mean(saturated, axis=0) >= HERO_OPTION_COLUMN_COVERAGE
    )

    # Text/effects can cut a very narrow vertical gap through an otherwise
    # solid card panel. Bridge those gaps before measuring the minimum card
    # width, while leaving the much wider spacing between cards untouched.
    inactive = ~active_columns
    gap_start: Optional[int] = None
    for x, is_inactive in enumerate(np.append(inactive, False)):
        if is_inactive and gap_start is None:
            gap_start = x
        elif not is_inactive and gap_start is not None:
            is_bounded = gap_start > 0 and x < active_columns.size
            if is_bounded and x - gap_start <= HERO_OPTION_MAX_COLUMN_GAP:
                active_columns[gap_start:x] = True
            gap_start = None

    runs: list[tuple[int, int]] = []
    run_start: Optional[int] = None
    for x, active in enumerate(np.append(active_columns, False)):
        if active and run_start is None:
            run_start = x
        elif not active and run_start is not None:
            if x - run_start >= HERO_OPTION_MIN_WIDTH:
                runs.append((run_start, x))
            run_start = None

    click_y = (HERO_OPTION_PANEL_TOP + HERO_OPTION_PANEL_BOTTOM) // 2
    return [((left + right - 1) // 2, click_y) for left, right in runs]


def hero_option_is_purple(
    frame_bgr: np.ndarray,
    center: tuple[int, int],
) -> bool:
    """Classify a card from the stable solid strip on its lower-right edge."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return False

    x, _y = center
    strip = frame_bgr[
        HERO_OPTION_COLOR_TOP:HERO_OPTION_COLOR_BOTTOM,
        max(0, x + HERO_OPTION_COLOR_LEFT_OFFSET):
        min(frame_bgr.shape[1], x + HERO_OPTION_COLOR_RIGHT_OFFSET),
    ]
    if strip.size == 0:
        return False

    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    colored = (
        (hsv[:, :, 1] >= HERO_OPTION_MIN_SATURATION)
        & (hsv[:, :, 2] >= HERO_OPTION_MIN_VALUE)
    )
    hues = hsv[:, :, 0][colored]
    if hues.size == 0:
        return False
    median_hue = float(np.median(hues))
    return HERO_OPTION_PURPLE_HUE_MIN <= median_hue <= HERO_OPTION_PURPLE_HUE_MAX


def find_hero_ascend_options(
    frame_gray: np.ndarray,
    template: np.ndarray,
    threshold: float = HERO_ASCEND_TEMPLATE_THRESHOLD,
) -> list[tuple[int, int, float]]:
    """Return all ascend-card centers found from their stable cyan corner."""
    if frame_gray.ndim != 2 or frame_gray.shape[0] <= HERO_LEVELUP_SEARCH_TOP:
        return []

    matches = find_template_matches(
        frame_gray[HERO_LEVELUP_SEARCH_TOP:, :],
        template,
        HERO_ASCEND_TEMPLATE_NAME,
        threshold=threshold,
        scales=(1.0,),
    )
    click_y = (HERO_OPTION_PANEL_TOP + HERO_OPTION_PANEL_BOTTOM) // 2
    return sorted(
        (
            (x + HERO_ASCEND_MATCH_CENTER_OFFSET_X, click_y, score)
            for x, _local_y, score in matches
        ),
        key=lambda match: match[0],
    )


class HeroLevelupMatcher:
    """Select a prioritized template, or any card when none is recognized."""

    def __init__(
        self,
        template_paths: tuple[Path, ...] = HERO_LEVELUP_TEMPLATE_PATHS,
        threshold: float = HERO_LEVELUP_TEMPLATE_THRESHOLD,
    ) -> None:
        self.threshold = threshold
        self.templates = tuple(
            (path, load_template(path)) for path in template_paths
        )

    def find_choice(self, frame_bgr: np.ndarray) -> Optional[HeroLevelupChoice]:
        if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            return None

        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        option_region = frame_gray[HERO_LEVELUP_SEARCH_TOP:, :]
        option_centers = find_hero_option_centers(frame_bgr)
        ignored_centers: set[tuple[int, int]] = set()
        for template_path, template in self.templates:
            priority = _template_priority(template_path)[0]
            if template_path.name == HERO_ASCEND_TEMPLATE_NAME:
                ascend_options = find_hero_ascend_options(
                    frame_gray,
                    template,
                    threshold=max(self.threshold, HERO_ASCEND_TEMPLATE_THRESHOLD),
                )
                if ascend_options:
                    x, y, score = ascend_options[0]
                    return HeroLevelupChoice(
                        x=x,
                        y=y,
                        template_name=template_path.name,
                        score=score,
                        priority=priority,
                    )
                continue

            x, local_y, score = find_template(
                option_region,
                template,
                template_path.name,
                scales=(1.0,),
            )
            required_score = (
                HERO_NAME_TEMPLATE_THRESHOLD
                if priority in HERO_NAME_TEMPLATE_PRIORITIES
                else self.threshold
            )
            if score < required_score:
                continue

            if priority >= HERO_IGNORED_PRIORITY and option_centers:
                ignored_centers.add(
                    min(option_centers, key=lambda center: abs(center[0] - x))
                )
                continue

            return HeroLevelupChoice(
                x=x,
                y=HERO_LEVELUP_SEARCH_TOP + local_y,
                template_name=template_path.name,
                score=score,
                priority=priority,
            )

        if not option_centers:
            return None
        fallback_centers = [
            center for center in option_centers if center not in ignored_centers
        ]
        eligible_centers = fallback_centers or option_centers
        purple_centers = [
            center
            for center in eligible_centers
            if hero_option_is_purple(frame_bgr, center)
        ]
        x, y = (purple_centers or eligible_centers)[0]
        # TEMP FALLBACK TRACKING: expose whether purple detection succeeded so
        # the flow can capture only the no-priority + no-purple cases.
        fallback_color = "purple" if purple_centers else "other"
        return HeroLevelupChoice(
            x=x,
            y=y,
            fallback_color=fallback_color,
            fallback_option_count=len(option_centers),
        )

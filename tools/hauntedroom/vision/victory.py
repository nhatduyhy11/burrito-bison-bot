"""Language-independent detection for the shared victory reward panel."""

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


GAME_CONTENT_WIDTH = 405
SIDE_STRIP_WIDTH = 12
SEARCH_TOP_RATIO = 0.20
SEARCH_BOTTOM_RATIO = 0.78
MIN_RED_ROW_RATIO = 0.75
MIN_PANEL_HEIGHT_RATIO = 0.08


@dataclass(frozen=True)
class VictoryPanel:
    top: int
    bottom: int


def _longest_true_run(values: np.ndarray) -> tuple[int, int]:
    padded = np.pad(values.astype(np.int8), (1, 1))
    transitions = np.diff(padded)
    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1)
    if starts.size == 0:
        return 0, 0
    lengths = ends - starts
    index = int(np.argmax(lengths))
    return int(starts[index]), int(lengths[index])


def find_victory_panel(frame_bgr: np.ndarray) -> Optional[VictoryPanel]:
    """Find the symmetric red side rails shared by game victory panels."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        return None

    height, width = frame_bgr.shape[:2]
    if height == 0 or width < SIDE_STRIP_WIDTH * 2:
        return None
    content_width = min(GAME_CONTENT_WIDTH, width)
    content_left = max((width - content_width) // 2, 0)
    content_right = content_left + content_width
    search_top = round(height * SEARCH_TOP_RATIO)
    search_bottom = round(height * SEARCH_BOTTOM_RATIO)
    if search_top >= search_bottom:
        return None

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    red = (
        ((hue <= 12) | (hue >= 165))
        & (saturation >= 80)
        & (value >= 35)
    )
    left_rows = red[
        search_top:search_bottom,
        content_left : content_left + SIDE_STRIP_WIDTH,
    ].mean(axis=1)
    right_rows = red[
        search_top:search_bottom,
        content_right - SIDE_STRIP_WIDTH : content_right,
    ].mean(axis=1)
    paired_rows = (left_rows >= MIN_RED_ROW_RATIO) & (
        right_rows >= MIN_RED_ROW_RATIO
    )
    start, run_length = _longest_true_run(paired_rows)
    if run_length < round(height * MIN_PANEL_HEIGHT_RATIO):
        return None
    top = search_top + start
    return VictoryPanel(top=top, bottom=top + run_length)


def victory_panel_visible(frame_bgr: np.ndarray) -> bool:
    return find_victory_panel(frame_bgr) is not None

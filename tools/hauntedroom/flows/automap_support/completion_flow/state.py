"""Shared state, results, and runtime context for map completion."""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

import numpy as np


class CompletionStep(Enum):
    NOT_HANDLED = auto()
    CONTINUE = auto()
    STOP = auto()


@dataclass(frozen=True)
class MapCompletionOutcome:
    completed: bool
    win_recorded: bool
    total_win: Optional[int]
    first_win_done: bool


@dataclass
class MapCompletionState:
    first_win_done: bool
    win_recorded: bool
    total_win: Optional[int]
    reward_followup_click_count: int = 0
    reward_click_position: Optional[tuple[int, int]] = None
    reward_list_title_seen: bool = False

    def outcome(self, completed: bool) -> MapCompletionOutcome:
        return MapCompletionOutcome(
            completed=completed,
            win_recorded=self.win_recorded,
            total_win=self.total_win,
            first_win_done=self.first_win_done,
        )


@dataclass(frozen=True)
class FirstWinContext:
    page: object
    stop_event: object
    daily_first_win_template: np.ndarray
    daily_first_win_template_path: Path
    daily_first_win_checkbox_template: np.ndarray
    daily_first_win_checkbox_template_path: Path
    daily_first_win_checked_template: np.ndarray
    daily_first_win_checked_template_path: Path
    capture_page_bgr_fn: Callable
    to_grayscale_fn: Callable
    find_template_fn: Callable
    click_fn: Callable
    wait_for_flow_timeout_fn: Callable
    flow_checkpoint_fn: Callable
    poll_ms: int


@dataclass(frozen=True)
class MapRewardContext:
    page: object
    stop_event: object
    win_reward_template: np.ndarray
    win_reward_template_path: Path
    reward_list_title_template: np.ndarray
    reward_list_title_template_path: Path
    on_win: Optional[Callable[[], int]]
    find_template_fn: Callable
    find_template_matches_fn: Callable
    click_fn: Callable
    wait_for_flow_timeout_fn: Callable


@dataclass(frozen=True)
class MapCompletionBlockerContext:
    page: object
    stop_event: object
    blocker_templates: tuple[tuple[Path, np.ndarray], ...]
    find_template_fn: Callable
    click_fn: Callable
    wait_for_flow_timeout_fn: Callable
    poll_ms: int


@dataclass(frozen=True)
class MapCompletionContext:
    page: object
    stop_event: object
    first_win: FirstWinContext
    reward: MapRewardContext
    blocker: MapCompletionBlockerContext
    start_home_template: np.ndarray
    start_home_template_path: Path
    capture_page_bgr_fn: Callable
    to_grayscale_fn: Callable
    find_template_fn: Callable
    wait_for_flow_timeout_fn: Callable
    flow_checkpoint_fn: Callable
    poll_ms: int

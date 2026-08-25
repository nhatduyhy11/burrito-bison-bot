"""Models and mutable state for a map and its enclosing run."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

import numpy as np


class MapLifecycleStep(Enum):
    NOT_HANDLED = auto()
    CONTINUE = auto()
    STOP = auto()


@dataclass(frozen=True)
class MapEndOutcome:
    handled: bool
    completed: bool = False


@dataclass(frozen=True)
class MapOutcome:
    completed: bool
    win_recorded: bool
    total_win: Optional[int]
    first_win_done: bool


@dataclass
class MapState:
    """All mutable state whose lifetime is one map."""

    last_map_end_check: float | None = None
    completed: bool = False
    win_recorded: bool = False
    total_win: int | None = None
    first_win_done: bool = False
    reward_followup_click_count: int = 0
    reward_click_position: tuple[int, int] | None = None
    reward_list_title_seen: bool = False
    final_boss_pet_deployed: bool = False
    boss_detection_logged: bool = False
    initial_gear_unlocked: bool = False
    initial_gear_attempted: bool = False
    initial_gear_placed: bool = False

    def outcome(self, completed: bool) -> MapOutcome:
        return MapOutcome(
            completed=completed,
            win_recorded=self.win_recorded,
            total_win=self.total_win,
            first_win_done=self.first_win_done,
        )


@dataclass
class MapRunState:
    """State shared by every map in one runner-owned command invocation."""

    daily_first_win_done: bool = False
    new_account_lubu_popup_active: bool = False


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
class MapBlockerContext:
    page: object
    stop_event: object
    blocker_templates: tuple[tuple[Path, np.ndarray], ...]
    find_template_fn: Callable
    click_fn: Callable
    wait_for_flow_timeout_fn: Callable
    poll_ms: int


@dataclass(frozen=True)
class MapLifecycleContext:
    page: object
    stop_event: object
    first_win: FirstWinContext
    reward: MapRewardContext
    blocker: MapBlockerContext
    start_home_template: np.ndarray
    start_home_template_path: Path
    capture_page_bgr_fn: Callable
    to_grayscale_fn: Callable
    find_template_fn: Callable
    wait_for_flow_timeout_fn: Callable
    flow_checkpoint_fn: Callable
    poll_ms: int

"""Mutable state owned by one auto-map flow."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AutomapState:
    last_map_end_check: float | None = None
    map_completed: bool = False
    win_recorded: bool = False
    total_win: int | None = None
    first_win_done: bool = False
    final_boss_pet_deployed: bool = False
    boss_detection_logged: bool = False
    initial_gear_unlocked: bool = False
    initial_gear_attempted: bool = False
    initial_gear_placed: bool = False

"""Loaded image resources used by auto-map."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from hauntedroom.core.template_matching import load_template
from hauntedroom.flows.automap_support.vision.template_config import AutomapConfig

TemplateLoader = Callable[[Path], np.ndarray]


@dataclass
class AutomapTemplates:
    lv_up: np.ndarray
    built: np.ndarray
    lv_spin: np.ndarray
    map_end: np.ndarray
    win_reward: np.ndarray
    reward_list_title: np.ndarray
    daily_first_win: np.ndarray
    daily_first_win_checkbox: np.ndarray
    daily_first_win_checked: np.ndarray
    boss_hp: np.ndarray
    start_home: np.ndarray
    exit_click: np.ndarray
    map_blockers: tuple[tuple[Path, np.ndarray], ...]
    hero_levelup: dict[Path, np.ndarray]

    @classmethod
    def load(
        cls,
        config: AutomapConfig,
        *,
        load_template_fn: TemplateLoader | None = None,
    ) -> AutomapTemplates:
        """Load one independent template set for a flow."""
        loader = load_template_fn or load_template
        return cls(
            lv_up=loader(config.lv_up_template_path),
            built=loader(config.built_template_path),
            lv_spin=loader(config.lv_spin_template_path),
            map_end=loader(config.map_end_template_path),
            win_reward=loader(config.win_reward_template_path),
            reward_list_title=loader(config.reward_list_title_template_path),
            daily_first_win=loader(config.daily_first_win_template_path),
            daily_first_win_checkbox=loader(
                config.daily_first_win_checkbox_template_path
            ),
            daily_first_win_checked=loader(
                config.daily_first_win_checked_template_path
            ),
            boss_hp=loader(config.boss_hp_template_path),
            start_home=loader(config.start_home_template_path),
            exit_click=loader(config.exit_click_template_path),
            map_blockers=tuple(
                (path, loader(path))
                for path in config.map_blocker_template_paths
            ),
            hero_levelup={
                path: loader(path) for path in config.hero_levelup_template_paths
            },
        )

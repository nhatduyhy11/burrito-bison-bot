"""Loaded image resources used by auto-map."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from hauntedroom.core.template_matching import load_template
from hauntedroom.flows.automap_support.config import AutomapConfig
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    load_hero_levelup_templates,
)

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
    map_completion_blockers: tuple[tuple[Path, np.ndarray], ...]
    hero_levelup: dict[Path, np.ndarray]

    @classmethod
    def load(
        cls,
        config: AutomapConfig,
        *,
        load_template_fn: TemplateLoader = load_template,
    ) -> AutomapTemplates:
        """Load one independent template set for a flow."""
        return cls(
            lv_up=load_template_fn(config.lv_up_template_path),
            built=load_template_fn(config.built_template_path),
            lv_spin=load_template_fn(config.lv_spin_template_path),
            map_end=load_template_fn(config.map_end_template_path),
            win_reward=load_template_fn(config.win_reward_template_path),
            reward_list_title=load_template_fn(config.reward_list_title_template_path),
            daily_first_win=load_template_fn(config.daily_first_win_template_path),
            daily_first_win_checkbox=load_template_fn(
                config.daily_first_win_checkbox_template_path
            ),
            daily_first_win_checked=load_template_fn(
                config.daily_first_win_checked_template_path
            ),
            boss_hp=load_template_fn(config.boss_hp_template_path),
            start_home=load_template_fn(config.start_home_template_path),
            exit_click=load_template_fn(config.exit_click_template_path),
            map_completion_blockers=tuple(
                (path, load_template_fn(path))
                for path in config.map_completion_blocker_template_paths
            ),
            hero_levelup=load_hero_levelup_templates(
                config.hero_levelup_template_paths
            ),
        )

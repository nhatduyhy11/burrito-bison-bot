"""Compatibility facade and composition root for one auto-map invocation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from hauntedroom.flows.automap_support.vision.template_config import (
    AUTOMAP_TEMPLATE_THRESHOLD,
    BOSS_HP_TEMPLATE_PATH,
    BUILT_TEMPLATE_PATH,
    DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH,
    DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH,
    DAILY_FIRST_WIN_TEMPLATE_PATH,
    EXIT_CLICK_TEMPLATE_PATH,
    LV_SPIN_TEMPLATE_PATH,
    LV_UP_TEMPLATE_PATH,
    MAP_BLOCKER_TEMPLATE_PATHS,
    MAP_END_TEMPLATE_PATH,
    REWARD_LIST_TITLE_TEMPLATE_PATH,
    START_HOME_TEMPLATE_PATH,
    WIN_REWARD_TEMPLATE_PATH,
    AutomapConfig,
)
from hauntedroom.flows.automap_support.flow import (
    BOSS_RECHECK_INTERVAL_MS,
    AutomapFlow,
)
from hauntedroom.flows.automap_support.map.lifecycle import (
    MAP_END_CHECK_INTERVAL_SEC,
    MAP_END_TEMPLATE_THRESHOLD,
)
from hauntedroom.flows.automap_support.map.model_state import (
    MapRunState,
    MapState,
)
from hauntedroom.flows.automap_support.templates import AutomapTemplates
from hauntedroom.flows.automap_support.upgrade_action import AUTOMAP_POLL_MS
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_LEVELUP_TEMPLATE_PATHS,
)
from hauntedroom.settings import CAPTURE_HERO_FALLBACK_SCREENSHOTS

__all__ = [
    "AutomapConfig",
    "AutomapFlow",
    "MapRunState",
    "run_automap_flow",
]


async def run_automap_flow(
    page,
    stop_event: asyncio.Event | None = None,
    lv_up_template_path: Path = LV_UP_TEMPLATE_PATH,
    threshold: float = AUTOMAP_TEMPLATE_THRESHOLD,
    built_template_path: Path = BUILT_TEMPLATE_PATH,
    lv_spin_template_path: Path = LV_SPIN_TEMPLATE_PATH,
    map_end_template_path: Path = MAP_END_TEMPLATE_PATH,
    win_reward_template_path: Path = WIN_REWARD_TEMPLATE_PATH,
    reward_list_title_template_path: Path = REWARD_LIST_TITLE_TEMPLATE_PATH,
    daily_first_win_template_path: Path = DAILY_FIRST_WIN_TEMPLATE_PATH,
    daily_first_win_checkbox_template_path: Path = (
        DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
    ),
    daily_first_win_checked_template_path: Path = (
        DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
    ),
    boss_hp_template_path: Path = BOSS_HP_TEMPLATE_PATH,
    start_home_template_path: Path = START_HOME_TEMPLATE_PATH,
    exit_click_template_path: Path = EXIT_CLICK_TEMPLATE_PATH,
    map_blocker_template_paths: tuple[Path, ...] = MAP_BLOCKER_TEMPLATE_PATHS,
    hero_levelup_template_paths: tuple[Path, ...] = HERO_LEVELUP_TEMPLATE_PATHS,
    capture_hero_fallback_screenshots: bool = CAPTURE_HERO_FALLBACK_SCREENSHOTS,
    debug: bool = False,
    on_win: Callable[[], int] | None = None,
    run_state: MapRunState | None = None,
) -> bool:
    """Build and run one auto-map flow while preserving the public API."""
    config = AutomapConfig(
        lv_up_template_path=lv_up_template_path,
        threshold=threshold,
        built_template_path=built_template_path,
        lv_spin_template_path=lv_spin_template_path,
        map_end_template_path=map_end_template_path,
        win_reward_template_path=win_reward_template_path,
        reward_list_title_template_path=reward_list_title_template_path,
        daily_first_win_template_path=daily_first_win_template_path,
        daily_first_win_checkbox_template_path=(
            daily_first_win_checkbox_template_path
        ),
        daily_first_win_checked_template_path=(
            daily_first_win_checked_template_path
        ),
        boss_hp_template_path=boss_hp_template_path,
        start_home_template_path=start_home_template_path,
        exit_click_template_path=exit_click_template_path,
        map_blocker_template_paths=map_blocker_template_paths,
        hero_levelup_template_paths=hero_levelup_template_paths,
        capture_hero_fallback_screenshots=capture_hero_fallback_screenshots,
        debug=debug,
    )
    templates = AutomapTemplates.load(config)
    state = MapState()
    return await AutomapFlow(
        page,
        stop_event,
        config=config,
        templates=templates,
        state=state,
        run_state=run_state,
        on_win=on_win,
    ).run()

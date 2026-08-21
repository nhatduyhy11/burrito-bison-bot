"""Immutable template configuration for one auto-map flow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_LEVELUP_TEMPLATE_PATHS,
)
from hauntedroom.settings import CAPTURE_HERO_FALLBACK_SCREENSHOTS

AUTOMAP_TEMPLATE_DIR = Path(__file__).resolve().parents[4] / "rooms" / "automap"
MAP_WIN_TEMPLATE_DIR = AUTOMAP_TEMPLATE_DIR / "map_win"
ROOM_TEMPLATE_DIR = AUTOMAP_TEMPLATE_DIR.parent
BOSS_TEMPLATE_DIR = ROOM_TEMPLATE_DIR / "boss"
BLOCKER_TEMPLATE_DIR = ROOM_TEMPLATE_DIR / "blocker"
LV_UP_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "lv_up.png"
BUILT_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "built.png"
LV_SPIN_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "lv_spin.png"
MAP_END_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "map_end.png"
WIN_REWARD_TEMPLATE_PATH = MAP_WIN_TEMPLATE_DIR / "win_reward.png"
REWARD_LIST_TITLE_TEMPLATE_PATH = MAP_WIN_TEMPLATE_DIR / "reward_list_title.png"
DAILY_FIRST_WIN_TEMPLATE_PATH = MAP_WIN_TEMPLATE_DIR / "daily_first_win.png"
DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH = (
    MAP_WIN_TEMPLATE_DIR / "daily_first_win_checkbox.png"
)
DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH = (
    MAP_WIN_TEMPLATE_DIR / "daily_first_win_checked.png"
)
BOSS_HP_TEMPLATE_PATH = BOSS_TEMPLATE_DIR / "boss_hp_bar.png"
START_HOME_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "start_home.png"
EXIT_CLICK_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "exit_click.png"
MAP_BLOCKER_TEMPLATE_PATHS = tuple(
    BLOCKER_TEMPLATE_DIR / name
    for name in (
        "lubu_close.png",
        "overlay_close.png",
        "overlay_close_2.png",
        "overlay_newbie.png",
    )
)

# lv_up.png excludes the two-pixel background border. The two valid icons in
# the captured battle UI score about 0.95 and 0.86; other UI stays below 0.60.
AUTOMAP_TEMPLATE_THRESHOLD = 0.80


@dataclass(frozen=True)
class AutomapConfig:
    """Game-specific settings used by exactly one auto-map flow."""

    lv_up_template_path: Path = LV_UP_TEMPLATE_PATH
    threshold: float = AUTOMAP_TEMPLATE_THRESHOLD
    built_template_path: Path = BUILT_TEMPLATE_PATH
    lv_spin_template_path: Path = LV_SPIN_TEMPLATE_PATH
    map_end_template_path: Path = MAP_END_TEMPLATE_PATH
    win_reward_template_path: Path = WIN_REWARD_TEMPLATE_PATH
    reward_list_title_template_path: Path = REWARD_LIST_TITLE_TEMPLATE_PATH
    daily_first_win_template_path: Path = DAILY_FIRST_WIN_TEMPLATE_PATH
    daily_first_win_checkbox_template_path: Path = (
        DAILY_FIRST_WIN_CHECKBOX_TEMPLATE_PATH
    )
    daily_first_win_checked_template_path: Path = DAILY_FIRST_WIN_CHECKED_TEMPLATE_PATH
    boss_hp_template_path: Path = BOSS_HP_TEMPLATE_PATH
    start_home_template_path: Path = START_HOME_TEMPLATE_PATH
    exit_click_template_path: Path = EXIT_CLICK_TEMPLATE_PATH
    map_blocker_template_paths: tuple[Path, ...] = MAP_BLOCKER_TEMPLATE_PATHS
    hero_levelup_template_paths: tuple[Path, ...] = HERO_LEVELUP_TEMPLATE_PATHS
    capture_hero_fallback_screenshots: bool = CAPTURE_HERO_FALLBACK_SCREENSHOTS
    debug: bool = False

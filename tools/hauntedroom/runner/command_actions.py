from pathlib import Path

from hauntedroom.actions.models import (
    Action,
    ClearBlockersAction,
    ClickAction,
    ClickHeroSelectBattleAction,
    ClickMapExitBackAction,
    ClickPauseExitAction,
    ClickTemplateAction,
)
from hauntedroom.control_events.blockers import NEWBIE_BLOCKER_DISMISS_CLICK


ROOMS_DIR = Path(__file__).resolve().parents[2] / "rooms"
BLOCKER_PRIORITY = (
    "lubu_close.png",
    "overlay_close.png",
    "overlay_close_2.png",
    "overlay_newbie.png",
)


def build_blocker_paths() -> tuple[Path, ...]:
    return tuple(ROOMS_DIR / "blocker" / name for name in BLOCKER_PRIORITY)


def build_start_battle_actions() -> list[Action]:
    """Build Shift+1 HOME entry actions from fixed Python configuration."""
    blocker_paths = build_blocker_paths()
    return [
        ClearBlockersAction(
            blocker_paths=blocker_paths,
            until_template_path=ROOMS_DIR / "start_home.png",
            until_template_scales=(1.0,),
            note="Before Start HOME",
        ),
        ClickTemplateAction(
            template_path=ROOMS_DIR / "start_home.png",
            click_position="mid_left",
            template_scales=(1.0,),
            click_count=3,
            recheck_before_repeat=True,
            repeat_delay_ms=1_000,
            note="Start HOME",
        ),
        ClickHeroSelectBattleAction(
            blocker_paths=blocker_paths,
            header_template_path=(
                ROOMS_DIR / "hero_select_battle_banner_top.png"
            ),
            entry_template_path=ROOMS_DIR / "start_home.png",
            note="Start Battle",
        ),
    ]


def build_spawn_exit_lvup_actions() -> list[Action]:
    """Build the fixed spawn/exit/level-up cycle used by Shift+9."""
    blocker_paths = build_blocker_paths()
    return [
        *build_start_battle_actions(),
        ClickTemplateAction(
            template_path=ROOMS_DIR / "exit_click.png",
            timeout_ms=60_000,
            note="Exit click",
        ),
        ClickPauseExitAction(
            note="Exit confirm",
        ),
        ClickMapExitBackAction(
            skip_if_template_path=ROOMS_DIR / "start_home.png",
            note="Exit Back",
        ),
        ClearBlockersAction(
            blocker_paths=blocker_paths,
            until_template_path=ROOMS_DIR / "start_home.png",
            until_template_scales=(1.0,),
            note="After Exit Back",
        ),
    ]


def build_newbie_block_actions() -> list[Action]:
    """Dismiss the detected newbie overlay at its fixed black margin."""
    x, y = NEWBIE_BLOCKER_DISMISS_CLICK
    return [
        ClickAction(
            x=x,
            y=y,
            note="Dismiss newbie block",
        )
    ]

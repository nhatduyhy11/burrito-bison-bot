from pathlib import Path
from hauntedroom.actions.models import (
    Action,
    ClearBlockersAction,
    ClickHeroSelectBattleAction,
    ClickMapExitBackAction,
    ClickPauseExitAction,
    ClickTemplateAction,
)

ROOMS_DIR = Path(__file__).resolve().parents[2] / "rooms"
# The pause icon is fixed in the upper-left control rail at the supported
# 640x720 viewport. Searching only this rail prevents game sprites from being
# mistaken for the tiny 22x24 icon.
PAUSE_TRIGGER_REGION = (120, 125, 175, 175)
BLOCKER_PRIORITY = (
    "lubu_close.png",
    "overlay_close.png",
    "overlay_close_2.png",
    "overlay_newbie.png",
)


def build_start_battle_actions() -> list[Action]:
    """Build Shift+1 HOME entry actions from fixed Python configuration."""
    blocker_paths = tuple(
        ROOMS_DIR / "blocker" / name for name in BLOCKER_PRIORITY
    )
    blocker_click_positions = {"overlay_newbie.png": "top_middle"}
    return [
        ClearBlockersAction(
            blocker_paths=blocker_paths,
            until_template_path=ROOMS_DIR / "start_home.png",
            click_positions=blocker_click_positions,
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
            click_positions=blocker_click_positions,
            note="Start Battle",
        ),
    ]


def build_spawn_exit_lvup_actions() -> list[Action]:
    """Build the fixed spawn/exit/level-up cycle used by Shift+9."""
    blocker_paths = tuple(
        ROOMS_DIR / "blocker" / name for name in BLOCKER_PRIORITY
    )
    blocker_click_positions = {"overlay_newbie.png": "top_middle"}
    return [
        *build_start_battle_actions(),
        ClickTemplateAction(
            template_path=ROOMS_DIR / "exit_click.png",
            threshold=0.70,  # Lowered threshold to handle newbie tooltip overlaps
            timeout_ms=60_000,
            template_scales=(1.0,),
            region=PAUSE_TRIGGER_REGION,
            note="Exit click",
        ),
        ClickPauseExitAction(
            retry_template_path=ROOMS_DIR / "exit_click.png",
            retry_template_threshold=0.70,
            retry_template_region=PAUSE_TRIGGER_REGION,
            note="Exit confirm",
        ),
        ClickMapExitBackAction(
            skip_if_template_path=ROOMS_DIR / "start_home.png",
            note="Exit Back",
        ),
        ClearBlockersAction(
            blocker_paths=blocker_paths,
            until_template_path=ROOMS_DIR / "start_home.png",
            click_positions=blocker_click_positions,
            until_template_scales=(1.0,),
            note="After Exit Back",
        ),
    ]

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from hauntedroom.actions.models import (
    Action,
    ClearBlockersAction,
    ClickTemplateAction,
)
from hauntedroom.core.runtime import FlowControl
from hauntedroom.flows.automap_support.state import AutomapRunContext


FlowStarter = Callable[[object, object, bool], Awaitable[object]]
FlowResolver = Callable[[list[Action], bool, Optional[Path]], "ResolvedFlow"]
ControlFactory = Callable[[], object]
ROOMS_DIR = Path(__file__).resolve().parents[2] / "rooms"
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
        ClearBlockersAction(
            blocker_paths=blocker_paths,
            until_template_path=ROOMS_DIR / "start_battle.png",
            click_positions=blocker_click_positions,
            note="Before Start Battle",
        ),
        ClickTemplateAction(
            template_path=ROOMS_DIR / "start_battle.png",
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
            timeout_ms=60_000,
            note="Exit click",
        ),
        ClickTemplateAction(
            template_path=ROOMS_DIR / "exit_confirm.png",
            note="Exit confirm",
        ),
        ClickTemplateAction(
            template_path=ROOMS_DIR / "exit_back.png",
            threshold=0.75,
            skip_if_template_path=ROOMS_DIR / "start_home.png",
            skip_template_scales=(1.0,),
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


@dataclass(frozen=True)
class ResolvedFlow:
    actions: list[Action]
    run: FlowStarter


@dataclass(frozen=True)
class FlowCommand:
    key: str
    name: str
    menu_label: str
    resolve: FlowResolver
    control_factory: ControlFactory = asyncio.Event
    uses_automap_controls: bool = False


def build_flow_commands(reload_policy, start_auto_flow) -> dict[str, FlowCommand]:
    def resolve_spawn_exit_lvup(
        _actions: list[Action],
        dev_reload: bool,
        _actions_path: Optional[Path],
    ) -> ResolvedFlow:
        action_runner = reload_policy.get_action_runner(dev_reload)
        spawn_exit_lvup_actions = build_spawn_exit_lvup_actions()

        async def run(page, stop_event, _debug: bool):
            return await action_runner(
                page,
                spawn_exit_lvup_actions,
                loop_count=None,
                stop_event=stop_event,
                loop_label="spawn_exit_lvup loop",
            )

        return ResolvedFlow(spawn_exit_lvup_actions, run)

    def resolve_automap(
        actions: list[Action],
        dev_reload: bool,
        _actions_path: Optional[Path],
    ) -> ResolvedFlow:
        automap_runtime = reload_policy.get_automap_runtime(dev_reload)

        async def run(page, stop_event, debug: bool):
            run_context = AutomapRunContext()
            return await automap_runtime.automap_flow(
                page,
                stop_event,
                debug=debug,
                run_context=run_context,
            )

        return ResolvedFlow(actions, run)

    def resolve_start_auto(
        actions: list[Action],
        dev_reload: bool,
        _actions_path: Optional[Path],
    ) -> ResolvedFlow:
        automap_runtime = reload_policy.get_automap_runtime(dev_reload)
        start_actions = build_start_battle_actions()

        async def run(page, stop_event, debug: bool):
            run_context = AutomapRunContext()
            return await start_auto_flow.run_start_automap_loop(
                page,
                start_actions,
                automap_runtime.automap_flow,
                stop_event,
                automap_runtime.action_runner,
                debug,
                run_context=run_context,
            )

        return ResolvedFlow(actions, run)

    def resolve_train(
        actions: list[Action],
        dev_reload: bool,
        _actions_path: Optional[Path],
    ) -> ResolvedFlow:
        automap_runtime = reload_policy.get_automap_runtime(dev_reload)
        train_flow = reload_policy.get_train_flow(dev_reload)

        async def run(page, stop_event, debug: bool):
            run_context = AutomapRunContext()
            return await train_flow(
                page,
                automap_runtime.automap_flow,
                stop_event,
                debug,
                run_context=run_context,
            )

        return ResolvedFlow(actions, run)

    def resolve_json_actions(
        actions: list[Action],
        dev_reload: bool,
        actions_path: Optional[Path],
    ) -> ResolvedFlow:
        if actions_path is None:
            raise ValueError("Shift+5 requires an action JSON path.")
        action_runner = reload_policy.get_action_runner(dev_reload)
        actions = reload_policy.load_actions(actions_path)
        print(f"Actions loaded from {actions_path}.", flush=True)

        async def run(page, stop_event, _debug: bool):
            return await action_runner(
                page,
                actions,
                loop_count=None,
                stop_event=stop_event,
            )

        return ResolvedFlow(actions, run)

    def resolve_research(
        actions: list[Action],
        dev_reload: bool,
        _actions_path: Optional[Path],
    ) -> ResolvedFlow:
        research_flow = reload_policy.get_research_flow(dev_reload)

        async def run(page, stop_event, _debug: bool):
            return await research_flow(page, stop_event)

        return ResolvedFlow(actions, run)

    def resolve_artifact(
        actions: list[Action],
        dev_reload: bool,
        _actions_path: Optional[Path],
    ) -> ResolvedFlow:
        artifact_flow = reload_policy.get_artifact_flow(dev_reload)

        async def run(page, stop_event, _debug: bool):
            return await artifact_flow(page, stop_event)

        return ResolvedFlow(actions, run)

    def resolve_exp_available(
        actions: list[Action],
        dev_reload: bool,
        _actions_path: Optional[Path],
    ) -> ResolvedFlow:
        exp_available_flow = reload_policy.get_exp_available_flow(dev_reload)

        async def run(page, stop_event, _debug: bool):
            return await exp_available_flow(page, stop_event)

        return ResolvedFlow(actions, run)

    def resolve_hero_up_available(
        actions: list[Action],
        dev_reload: bool,
        _actions_path: Optional[Path],
    ) -> ResolvedFlow:
        hero_up_available_flow = reload_policy.get_hero_up_available_flow(dev_reload)

        async def run(page, stop_event, _debug: bool):
            return await hero_up_available_flow(page, stop_event)

        return ResolvedFlow(actions, run)

    return {
        "spawn_exit_lvup": FlowCommand(
            "spawn_exit_lvup",
            "spawn_exit_lvup loop",
            "Spawn / exit / level-up loop",
            resolve_spawn_exit_lvup,
        ),
        "automap": FlowCommand(
            "automap",
            "auto-map battle",
            "Auto-map battle",
            resolve_automap,
            control_factory=FlowControl,
            uses_automap_controls=True,
        ),
        "start_auto": FlowCommand(
            "start_auto",
            "start-auto loop",
            "Start-auto loop / pause at final boss",
            resolve_start_auto,
            control_factory=FlowControl,
            uses_automap_controls=True,
        ),
        "train": FlowCommand(
            "train",
            "train then auto-battle",
            "Train mode then auto-battle",
            resolve_train,
        ),
        "exp_available": FlowCommand(
            "exp_available",
            "EXP available",
            "EXP available",
            resolve_exp_available,
        ),
        "hero_up_available": FlowCommand(
            "hero_up_available",
            "hero breakthrough available",
            "Hero breakthrough available",
            resolve_hero_up_available,
        ),
        "json_actions": FlowCommand(
            "json_actions",
            "JSON action loop",
            "Run JSON actions in a loop",
            resolve_json_actions,
        ),
        "research": FlowCommand(
            "research",
            "research",
            "Research",
            resolve_research,
        ),
        "artifact": FlowCommand(
            "artifact",
            "artifact",
            "Artifact",
            resolve_artifact,
        ),
    }

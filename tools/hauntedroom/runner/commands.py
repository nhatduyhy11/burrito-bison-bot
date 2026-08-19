import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from hauntedroom.actions.models import Action
from hauntedroom.core.runtime import FlowControl


FlowStarter = Callable[[object, object, bool], Awaitable[object]]
FlowResolver = Callable[[list[Action], bool, Optional[Path]], "ResolvedFlow"]
ControlFactory = Callable[[], object]


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
    def reload_actions_for_dev(
        actions: list[Action],
        dev_reload: bool,
        actions_path: Optional[Path],
    ) -> list[Action]:
        if not dev_reload or actions_path is None:
            return actions

        reloaded_actions = reload_policy.load_actions(actions_path)
        print(f"Actions reloaded from {actions_path}.", flush=True)
        return reloaded_actions

    def resolve_enter_exit(
        actions: list[Action],
        dev_reload: bool,
        actions_path: Optional[Path],
    ) -> ResolvedFlow:
        action_runner = reload_policy.get_action_runner(dev_reload)
        actions = reload_actions_for_dev(actions, dev_reload, actions_path)

        async def run(page, stop_event, _debug: bool):
            return await action_runner(
                page,
                actions,
                loop_count=None,
                stop_event=stop_event,
            )

        return ResolvedFlow(actions, run)

    def resolve_automap(
        actions: list[Action],
        dev_reload: bool,
        _actions_path: Optional[Path],
    ) -> ResolvedFlow:
        automap_runtime = reload_policy.get_automap_runtime(dev_reload)

        async def run(page, stop_event, debug: bool):
            return await automap_runtime.automap_flow(page, stop_event, debug=debug)

        return ResolvedFlow(actions, run)

    def resolve_start_auto(
        actions: list[Action],
        dev_reload: bool,
        actions_path: Optional[Path],
    ) -> ResolvedFlow:
        automap_runtime = reload_policy.get_automap_runtime(dev_reload)
        actions = reload_actions_for_dev(actions, dev_reload, actions_path)

        async def run(page, stop_event, debug: bool):
            return await start_auto_flow.run_start_automap_loop(
                page,
                actions,
                automap_runtime.automap_flow,
                stop_event,
                automap_runtime.action_runner,
                debug,
            )

        return ResolvedFlow(actions, run)

    def resolve_train(
        actions: list[Action],
        dev_reload: bool,
        actions_path: Optional[Path],
    ) -> ResolvedFlow:
        automap_runtime = reload_policy.get_automap_runtime(dev_reload)
        train_flow = reload_policy.get_train_flow(dev_reload)
        actions = reload_actions_for_dev(actions, dev_reload, actions_path)

        async def run(page, stop_event, debug: bool):
            return await train_flow(
                page,
                actions,
                automap_runtime.automap_flow,
                stop_event,
                debug,
            )

        return ResolvedFlow(actions, run)

    def resolve_click_loop(
        actions: list[Action],
        dev_reload: bool,
        _actions_path: Optional[Path],
    ) -> ResolvedFlow:
        click_loop_flow = reload_policy.get_click_loop_flow(dev_reload)

        async def run(page, stop_event, _debug: bool):
            return await click_loop_flow(page, stop_event)

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
        "enter_exit": FlowCommand(
            "enter_exit",
            "enter-exit room",
            "Enter / exit room",
            resolve_enter_exit,
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
        "click_loop": FlowCommand(
            "click_loop",
            "fixed-position click loop",
            "Click (440, 500) every 1s",
            resolve_click_loop,
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

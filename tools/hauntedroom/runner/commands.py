import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from hauntedroom.core.runtime import FlowControl
from hauntedroom.flows import start_auto
from hauntedroom.runner import reload as reload_policy


FlowStarter = Callable[[object, object, bool], Awaitable[object]]
FlowResolver = Callable[[list[dict], bool, Optional[Path]], "ResolvedFlow"]
ControlFactory = Callable[[], object]


@dataclass(frozen=True)
class ResolvedFlow:
    actions: list[dict]
    run: FlowStarter


@dataclass(frozen=True)
class FlowCommand:
    key: str
    name: str
    menu_label: str
    resolve: FlowResolver
    control_factory: ControlFactory = asyncio.Event


def reload_actions_for_dev(
    actions: list[dict],
    dev_reload: bool,
    actions_path: Optional[Path],
) -> list[dict]:
    if not dev_reload or actions_path is None:
        return actions

    reloaded_actions = reload_policy.load_actions(actions_path)
    print(f"Actions reloaded from {actions_path}.", flush=True)
    return reloaded_actions


def resolve_enter_exit(
    actions: list[dict],
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
    actions: list[dict],
    dev_reload: bool,
    _actions_path: Optional[Path],
) -> ResolvedFlow:
    automap_flow = reload_policy.get_automap_flow(dev_reload)

    async def run(page, stop_event, debug: bool):
        return await automap_flow(page, stop_event, debug=debug)

    return ResolvedFlow(actions, run)


def resolve_start_auto(
    actions: list[dict],
    dev_reload: bool,
    actions_path: Optional[Path],
) -> ResolvedFlow:
    automap_flow = reload_policy.get_automap_flow(dev_reload)
    action_runner = reload_policy.get_action_runner(False)
    actions = reload_actions_for_dev(actions, dev_reload, actions_path)

    async def run(page, stop_event, debug: bool):
        return await start_auto.run_start_automap_loop(
            page,
            actions,
            automap_flow,
            stop_event,
            action_runner,
            debug,
        )

    return ResolvedFlow(actions, run)


def resolve_click_loop(
    actions: list[dict],
    dev_reload: bool,
    _actions_path: Optional[Path],
) -> ResolvedFlow:
    click_loop_flow = reload_policy.get_click_loop_flow(dev_reload)

    async def run(page, stop_event, _debug: bool):
        return await click_loop_flow(page, stop_event)

    return ResolvedFlow(actions, run)


def resolve_research(
    actions: list[dict],
    dev_reload: bool,
    _actions_path: Optional[Path],
) -> ResolvedFlow:
    research_flow = reload_policy.get_research_flow(dev_reload)

    async def run(page, stop_event, _debug: bool):
        return await research_flow(page, stop_event)

    return ResolvedFlow(actions, run)


FLOW_COMMANDS = {
    "1": FlowCommand(
        "1",
        "enter-exit room",
        "Enter / exit room",
        resolve_enter_exit,
    ),
    "2": FlowCommand(
        "2",
        "auto-map battle",
        "Auto-map battle",
        resolve_automap,
    ),
    "3": FlowCommand(
        "3",
        "start-auto loop",
        "Start-auto loop / pause / resume",
        resolve_start_auto,
        control_factory=FlowControl,
    ),
    "7": FlowCommand(
        "7",
        "fixed-position click loop",
        "Click (440, 500) every 1s",
        resolve_click_loop,
    ),
    "9": FlowCommand(
        "9",
        "research",
        "Research",
        resolve_research,
    ),
}


def format_flow_menu() -> str:
    return "\n".join(
        f"  Shift+{command.key}    {command.menu_label}"
        for command in FLOW_COMMANDS.values()
    )


def start_resolved_flow(
    command: FlowCommand,
    page,
    resolved: ResolvedFlow,
    stop_event,
    debug: bool,
):
    print(f"Starting {command.name} flow...", flush=True)
    return asyncio.create_task(resolved.run(page, stop_event, debug))

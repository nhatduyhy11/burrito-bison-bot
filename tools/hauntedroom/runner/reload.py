import importlib
from typing import NamedTuple

from hauntedroom import settings
from hauntedroom.actions import loader as actions_loader
from hauntedroom.actions import runner as actions_runner
from hauntedroom.control_events import blockers as control_blockers
from hauntedroom.control_events import new_tab_blocker
from hauntedroom.core import template, vision
from hauntedroom.flows import automap, click_loop, research, train
from hauntedroom.flows.automap_support import (
    boss_action,
    boss_detector,
    boss_flow,
    detectors,
    gear_action,
    hero_action,
    hero_levelup,
    map_completion,
    train_select,
    upgrade_action,
)
from hauntedroom.flows.click_loop import run_click_loop
from hauntedroom.flows.research import run_research_flow

load_actions = actions_loader.load_actions
run_actions = actions_runner.run_actions


class AutomapRuntime(NamedTuple):
    automap_flow: object
    action_runner: object


def reload_action_modules():
    """Reload modules used by JSON action flows and refresh imported callables."""
    global load_actions, run_actions

    importlib.invalidate_caches()
    importlib.reload(template)
    importlib.reload(vision)
    importlib.reload(new_tab_blocker)
    importlib.reload(control_blockers)
    reloaded_loader = importlib.reload(actions_loader)
    reloaded_runner = importlib.reload(actions_runner)
    load_actions = reloaded_loader.load_actions
    run_actions = reloaded_runner.run_actions
    print("Action support modules reloaded.", flush=True)
    return run_actions


def get_action_runner(dev_reload: bool = False):
    if not dev_reload:
        return run_actions
    return reload_action_modules()


def get_click_loop_flow(dev_reload: bool = False):
    global run_click_loop

    if not dev_reload:
        return run_click_loop

    importlib.invalidate_caches()
    reloaded_click_loop = importlib.reload(click_loop)
    run_click_loop = reloaded_click_loop.run_click_loop
    print("Click-loop module reloaded.", flush=True)
    return run_click_loop


def get_research_flow(dev_reload: bool = False):
    global run_research_flow

    if not dev_reload:
        return run_research_flow

    importlib.invalidate_caches()
    importlib.reload(template)
    importlib.reload(vision)
    reloaded_research = importlib.reload(research)
    run_research_flow = reloaded_research.run_research_flow
    print("Research modules reloaded.", flush=True)
    return run_research_flow


def get_automap_flow(dev_reload: bool = False):
    return get_automap_runtime(dev_reload).automap_flow


def get_train_flow(dev_reload: bool = False):
    if not dev_reload:
        return train.run_train_flow

    importlib.invalidate_caches()
    importlib.reload(train_select)
    reloaded_train = importlib.reload(train)
    print("Train modules reloaded.", flush=True)
    return reloaded_train.run_train_flow


def get_automap_runtime(dev_reload: bool = False) -> AutomapRuntime:
    if not dev_reload:
        return AutomapRuntime(automap.run_automap_flow, run_actions)

    action_runner = reload_action_modules()
    importlib.reload(settings)
    importlib.reload(boss_detector)
    importlib.reload(detectors)
    importlib.reload(boss_action)
    importlib.reload(gear_action)
    importlib.reload(hero_levelup)
    importlib.reload(map_completion)
    importlib.reload(upgrade_action)
    importlib.reload(hero_action)
    importlib.reload(boss_flow)
    reloaded_automap = importlib.reload(automap)
    print("Auto-map support modules reloaded.", flush=True)
    return AutomapRuntime(reloaded_automap.run_automap_flow, action_runner)

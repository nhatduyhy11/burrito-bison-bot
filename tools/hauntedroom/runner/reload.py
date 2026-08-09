import importlib

from hauntedroom import settings
from hauntedroom.actions import loader as actions_loader
from hauntedroom.actions import runner as actions_runner
from hauntedroom.actions.loader import load_actions
from hauntedroom.actions.runner import run_actions
from hauntedroom.control_events import blockers as control_blockers
from hauntedroom.control_events import new_tab_blocker
from hauntedroom.core import template, vision
from hauntedroom.flows import automap
from hauntedroom.flows import click_loop
from hauntedroom.flows import research
from hauntedroom.flows.automap_support import (
    boss_action,
    boss_detector,
    boss_flow,
    detectors,
    gear_action,
    hero_action,
    hero_levelup,
    map_completion,
    upgrade_action,
)
from hauntedroom.flows.click_loop import run_click_loop
from hauntedroom.flows.research import run_research_flow


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
    if not dev_reload:
        return automap.run_automap_flow

    reload_action_modules()
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
    return reloaded_automap.run_automap_flow

import importlib
from typing import NamedTuple

from hauntedroom import settings
from hauntedroom.actions import loader as actions_loader
from hauntedroom.actions import runner as actions_runner
from hauntedroom.control_events import blockers as control_blockers
from hauntedroom.control_events import new_tab_blocker
from hauntedroom.core import template_detection, template_matching, vision
from hauntedroom.flows import (
    artifact,
    automap,
    exp_available,
    hero_up_available,
    new_account,
    research,
    train,
)
from hauntedroom.flows.artifact import run_artifact_flow
from hauntedroom.flows.automap_support import (
    boss_action,
    boss_flow,
    flow as automap_flow_support,
    gear_action,
    hero_action,
    train_select,
    upgrade_action,
)
from hauntedroom.flows.automap_support.map import (
    blocker,
    first_win,
    lifecycle,
    model_state,
    reward,
)
from hauntedroom.flows.automap_support.vision import (
    boss_controls as boss_controls_vision,
)
from hauntedroom.flows.automap_support.vision import (
    boss_hp as boss_hp_vision,
)
from hauntedroom.flows.automap_support.vision import (
    boss_progress as boss_progress_vision,
)
from hauntedroom.flows.automap_support.vision import (
    build as build_vision,
)
from hauntedroom.flows.automap_support.vision import (
    gear as gear_vision,
)
from hauntedroom.flows.automap_support.vision import (
    hero_levelup as hero_levelup_vision,
)
from hauntedroom.flows.automap_support.vision import (
    train as train_vision,
)
from hauntedroom.flows.exp_available import run_exp_available_flow
from hauntedroom.flows.hero_up_available import run_hero_up_available_flow
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
    importlib.reload(template_matching)
    importlib.reload(vision)
    importlib.reload(template_detection)
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


def get_research_flow(dev_reload: bool = False):
    global run_research_flow

    if not dev_reload:
        return run_research_flow

    importlib.invalidate_caches()
    importlib.reload(template_matching)
    importlib.reload(vision)
    reloaded_research = importlib.reload(research)
    run_research_flow = reloaded_research.run_research_flow
    print("Research modules reloaded.", flush=True)
    return run_research_flow


def get_artifact_flow(dev_reload: bool = False):
    global run_artifact_flow

    if not dev_reload:
        return run_artifact_flow

    importlib.invalidate_caches()
    importlib.reload(template_matching)
    importlib.reload(vision)
    reloaded_artifact = importlib.reload(artifact)
    run_artifact_flow = reloaded_artifact.run_artifact_flow
    print("Artifact modules reloaded.", flush=True)
    return run_artifact_flow


def get_exp_available_flow(dev_reload: bool = False):
    global run_exp_available_flow

    if not dev_reload:
        return run_exp_available_flow

    importlib.invalidate_caches()
    importlib.reload(vision)
    reloaded_exp_available = importlib.reload(exp_available)
    run_exp_available_flow = reloaded_exp_available.run_exp_available_flow
    print("EXP available module reloaded.", flush=True)
    return run_exp_available_flow


def get_hero_up_available_flow(dev_reload: bool = False):
    global run_hero_up_available_flow

    if not dev_reload:
        return run_hero_up_available_flow

    importlib.invalidate_caches()
    importlib.reload(vision)
    reloaded_hero_up_available = importlib.reload(hero_up_available)
    run_hero_up_available_flow = (
        reloaded_hero_up_available.run_hero_up_available_flow
    )
    print("Hero breakthrough module reloaded.", flush=True)
    return run_hero_up_available_flow


def get_new_account_flow(dev_reload: bool = False):
    if not dev_reload:
        return new_account.run_new_account_flow

    importlib.invalidate_caches()
    importlib.reload(vision)
    reloaded_new_account = importlib.reload(new_account)
    print("New-account module reloaded.", flush=True)
    return reloaded_new_account.run_new_account_flow


def get_automap_flow(dev_reload: bool = False):
    return get_automap_runtime(dev_reload).automap_flow


def get_train_flow(dev_reload: bool = False):
    if not dev_reload:
        return train.run_train_flow

    importlib.invalidate_caches()
    importlib.reload(hero_levelup_vision)
    importlib.reload(train_vision)
    importlib.reload(train_select)
    reloaded_train = importlib.reload(train)
    print("Train modules reloaded.", flush=True)
    return reloaded_train.run_train_flow


def get_automap_runtime(dev_reload: bool = False) -> AutomapRuntime:
    if not dev_reload:
        return AutomapRuntime(automap.run_automap_flow, run_actions)

    action_runner = reload_action_modules()
    importlib.reload(settings)
    importlib.reload(boss_controls_vision)
    importlib.reload(boss_hp_vision)
    importlib.reload(boss_progress_vision)
    importlib.reload(build_vision)
    importlib.reload(gear_vision)
    importlib.reload(hero_levelup_vision)
    importlib.reload(boss_action)
    importlib.reload(gear_action)
    importlib.reload(model_state)
    importlib.reload(first_win)
    importlib.reload(reward)
    importlib.reload(blocker)
    importlib.reload(lifecycle)
    importlib.reload(upgrade_action)
    importlib.reload(hero_action)
    importlib.reload(boss_flow)
    importlib.reload(automap_flow_support)
    reloaded_automap = importlib.reload(automap)
    print("Auto-map support modules reloaded.", flush=True)
    return AutomapRuntime(reloaded_automap.run_automap_flow, action_runner)

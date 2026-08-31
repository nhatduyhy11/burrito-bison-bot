from dataclasses import replace

from hauntedroom.flows import start_auto
from hauntedroom.runner import reload as reload_policy
from hauntedroom.runner.commands import build_flow_commands
from hauntedroom.screen_detect import ScreenName


FLOW_DEFINITIONS = build_flow_commands(reload_policy, start_auto)

# Only these commands remain directly startable. The original command table is
# kept private so screen auto-switching can reuse its resolvers and reload policy.
FLOW_COMMANDS = {
    "t": replace(FLOW_DEFINITIONS["train_ad_exit"], key="T"),
    "5": replace(FLOW_DEFINITIONS["json_actions"], key="5"),
    "9": replace(FLOW_DEFINITIONS["spawn_exit_lvup"], key="9"),
}

SCREEN_FLOW_COMMANDS = {
    ScreenName.HOME: FLOW_DEFINITIONS["start_auto"],
    ScreenName.RESEARCH: FLOW_DEFINITIONS["research"],
    ScreenName.ARTIFACT: FLOW_DEFINITIONS["artifact"],
    ScreenName.DIAMOND_COLLECTION: FLOW_DEFINITIONS["diamond_collection"],
    ScreenName.EXP_HERO: FLOW_DEFINITIONS["exp_available"],
    ScreenName.HERO_AVAILABLE: FLOW_DEFINITIONS["hero_up_available"],
    ScreenName.TRAIN: FLOW_DEFINITIONS["train"],
    ScreenName.NEW_ACCOUNT: FLOW_DEFINITIONS["new_account"],
    ScreenName.AUTOMAP: FLOW_DEFINITIONS["automap"],
}

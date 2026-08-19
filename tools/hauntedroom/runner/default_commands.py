from dataclasses import replace

from hauntedroom.flows import start_auto
from hauntedroom.runner import reload as reload_policy
from hauntedroom.runner.commands import build_flow_commands
from hauntedroom.screen_detect import ScreenName


FLOW_DEFINITIONS = build_flow_commands(reload_policy, start_auto)

# Only these commands remain directly startable. The original command table is
# kept private so screen auto-switching can reuse its resolvers and reload policy.
FLOW_COMMANDS = {
    "t": replace(FLOW_DEFINITIONS["train"], key="T"),
    "5": replace(FLOW_DEFINITIONS["click_loop"], key="5"),
}

SCREEN_FLOW_COMMANDS = {
    ScreenName.HOME: FLOW_DEFINITIONS["start_auto"],
    ScreenName.RESEARCH: FLOW_DEFINITIONS["research"],
    ScreenName.ARTIFACT: FLOW_DEFINITIONS["artifact"],
    ScreenName.EXP_HERO: FLOW_DEFINITIONS["exp_available"],
    ScreenName.HERO_AVAILABLE: FLOW_DEFINITIONS["hero_up_available"],
    ScreenName.AUTOMAP: FLOW_DEFINITIONS["automap"],
}

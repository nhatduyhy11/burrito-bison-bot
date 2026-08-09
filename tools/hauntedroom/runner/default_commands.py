from hauntedroom.flows import start_auto
from hauntedroom.runner import reload as reload_policy
from hauntedroom.runner.commands import build_flow_commands


FLOW_COMMANDS = build_flow_commands(reload_policy, start_auto)

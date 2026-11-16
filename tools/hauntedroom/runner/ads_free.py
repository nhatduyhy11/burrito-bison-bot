"""Shift+A / Shift+D: override perform AdsFree (120) so ad buttons resolve SUCCESS
without the SDK. A page reload drops the override. See docs/client/SHOW_ADVERTISE.md."""

from hauntedroom.control_events.battle_speed import find_game_frame
from hauntedroom.core.terminal import BLUE, ORANGE, colorize

ADS_FREE_COMMANDS = {"a": True, "d": False}

ADS_FREE_SCRIPT = """on => {
  const m = window.__require("SDKMgr").SDKMgr.Ins;
  if (on && !m.__adsFreeOrig) {
    m.__adsFreeOrig = m.getPerformConfig;
    m.getPerformConfig = function (key, dflt) { return key === 120 || m.__adsFreeOrig.call(this, key, dflt); };
  } else if (!on && m.__adsFreeOrig) {
    m.getPerformConfig = m.__adsFreeOrig;
    delete m.__adsFreeOrig;
  }
  return !!m.__adsFreeOrig;
}"""


async def handle_ads_free_command(page, command: str) -> bool:
    if command not in ADS_FREE_COMMANDS:
        return False
    frame = await find_game_frame(page)
    if frame is None:
        print(colorize("[ads] game frame not found.", ORANGE), flush=True)
        return True
    on = await frame.evaluate(ADS_FREE_SCRIPT, ADS_FREE_COMMANDS[command])
    print(colorize(f"[ads] free {'ON' if on else 'OFF'}", BLUE if on else ORANGE), flush=True)
    return True

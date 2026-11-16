"""Shift+A / Shift+D: client-side unlocks on/off.

- Ads free: perform AdsFree (120) -> ad buttons resolve SUCCESS without the SDK
  (docs/client/SHOW_ADVERTISE.md).
- Battle X2 + AI (auto): `UnlockMgr.checkPass(BattleSpeed = 9003 | BattleAI = 9007)`
  -> allow (docs/planning/2026-11-16-battle-x2-ai-gate.md). Takes effect when the battle
  UI next checks it (enter a new battle if a button is already locked). X2 leaves
  `SetSpeed 1.6` ops in the QuitRoom upload.

A page reload drops both overrides."""

from hauntedroom.control_events.battle_speed import find_game_frame
from hauntedroom.core.terminal import BLUE, ORANGE, colorize

ADS_FREE_COMMANDS = {"a": True, "d": False}

ADS_FREE_SCRIPT = """on => {
  const UNLOCK_IDS = [9003, 9007];  // BattleSpeed (X2), BattleAI (auto)
  const sdk = window.__require("SDKMgr").SDKMgr.Ins;
  const unlock = window.__require("UnlockMgr").UnlockMgr.Ins;
  if (on && !sdk.__adsFreeOrig) {
    sdk.__adsFreeOrig = sdk.getPerformConfig;
    sdk.getPerformConfig = function (key, dflt) { return key === 120 || sdk.__adsFreeOrig.call(this, key, dflt); };
  } else if (!on && sdk.__adsFreeOrig) {
    sdk.getPerformConfig = sdk.__adsFreeOrig;
    delete sdk.__adsFreeOrig;
  }
  if (on && !unlock.__aiOrig) {
    unlock.__aiOrig = unlock.checkPass;
    unlock.checkPass = function (id) {
      const r = unlock.__aiOrig.apply(this, arguments);
      if (UNLOCK_IDS.includes(Number(id))) r.allow = true;
      return r;
    };
  } else if (!on && unlock.__aiOrig) {
    unlock.checkPass = unlock.__aiOrig;
    delete unlock.__aiOrig;
  }
  return !!sdk.__adsFreeOrig && !!unlock.__aiOrig;
}"""


async def handle_ads_free_command(page, command: str) -> bool:
    if command not in ADS_FREE_COMMANDS:
        return False
    frame = await find_game_frame(page)
    if frame is None:
        print(colorize("[unlock] game frame not found.", ORANGE), flush=True)
        return True
    on = await frame.evaluate(ADS_FREE_SCRIPT, ADS_FREE_COMMANDS[command])
    state = "ON" if on else "OFF"
    print(colorize(f"[unlock] ads free + battle X2/AI {state}", BLUE if on else ORANGE), flush=True)
    return True

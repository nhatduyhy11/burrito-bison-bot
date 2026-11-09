"""Client-side campaign battle speed override (POC).

The game resets ``timeScale`` from the battle's ``SetSpeed`` operation using the
speed cached per battle type, so the override writes both the cache
(``BattleModule.setSpeedByBattleType``) and the live ``BattleMainLoop``. The
original cached speed is remembered in the page and restored on disable.
See ``scripts/SPEED_MODIFIER.md`` for the runtime evidence.
"""

from dataclasses import dataclass
from typing import Optional

CAMPAIGN_BATTLE_TYPE = 3  # EBattleType_Battle_Enum.EBattleTypeHangUpSystem

_FIND_MAIN_LOOP = """
const findMainLoop = () => {
  if (typeof window.__require !== "function" || typeof cc === "undefined") return null;
  const scene = cc.director.getScene();
  if (!scene) return null;
  const L = window.__require("BattleMainLoop").BattleMainLoop;
  const m = scene.getComponentInChildren(L);
  return m && m._battleUUID ? m : null;
};
const battleModule = () => window.__require("BattleModule").BattleModule.Ins;
"""

STATUS_SCRIPT = (
    "() => {"
    + _FIND_MAIN_LOOP
    + """
  if (typeof window.__require !== "function") return null;
  const m = findMainLoop();
  const vo = m && m.blackBoard && m.blackBoard.battleVo;
  return {
    inBattle: !!m,
    battleType: vo ? vo.battleType : null,
    timeScale: m && m.frameSync ? m.frameSync.timeScale : null,
    active: !!window.__hauntedRoomSpeed,
  };
}"""
)

APPLY_SCRIPT = (
    "([scale, battleType]) => {"
    + _FIND_MAIN_LOOP
    + """
  const m = findMainLoop();
  if (!m) return {applied: false, reason: "no battle"};
  const vo = m.blackBoard && m.blackBoard.battleVo;
  if (!vo || vo.battleType !== battleType) {
    return {applied: false, reason: "battle type " + (vo && vo.battleType)};
  }
  const bm = battleModule();
  if (!window.__hauntedRoomSpeed) {
    window.__hauntedRoomSpeed = {storedOriginal: bm.getSpeedByBattleType(battleType), battleType};
  }
  if (bm.getSpeedByBattleType(battleType) !== scale) bm.setSpeedByBattleType(battleType, scale);
  const before = m.frameSync.timeScale;
  if (before !== scale) m.setTimeScale(scale);
  return {applied: true, before, timeScale: m.frameSync.timeScale};
}"""
)

RESTORE_SCRIPT = (
    "() => {"
    + _FIND_MAIN_LOOP
    + """
  const state = window.__hauntedRoomSpeed;
  if (!state) return {restored: false};
  const bm = battleModule();
  bm.setSpeedByBattleType(state.battleType, state.storedOriginal);
  const m = findMainLoop();
  if (m) m.setTimeScale(state.storedOriginal);
  delete window.__hauntedRoomSpeed;
  return {restored: true, speed: state.storedOriginal, inBattle: !!m};
}"""
)


@dataclass(frozen=True)
class BattleSpeedStatus:
    in_battle: bool
    battle_type: Optional[int]
    time_scale: Optional[float]
    active: bool


async def find_game_frame(page):
    """Return the frame that hosts the Cocos game module loader."""
    for frame in [page.main_frame, *page.frames]:
        try:
            if await frame.evaluate(
                "() => typeof window.__require === 'function' && typeof cc !== 'undefined'"
            ):
                return frame
        except Exception:
            continue
    return None


async def read_battle_speed(frame) -> Optional[BattleSpeedStatus]:
    result = await frame.evaluate(STATUS_SCRIPT)
    if result is None:
        return None
    return BattleSpeedStatus(
        in_battle=bool(result["inBattle"]),
        battle_type=result["battleType"],
        time_scale=result["timeScale"],
        active=bool(result["active"]),
    )


async def apply_battle_speed(
    frame, scale: float, battle_type: int = CAMPAIGN_BATTLE_TYPE
) -> dict:
    """Set cached + live speed; idempotent so a watcher can re-apply after resets."""
    return await frame.evaluate(APPLY_SCRIPT, [scale, battle_type])


async def restore_battle_speed(frame) -> dict:
    return await frame.evaluate(RESTORE_SCRIPT)

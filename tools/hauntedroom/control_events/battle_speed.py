"""Isolated runtime speed override for the current battle; no battle-type cache."""

_FIND_MAIN_LOOP = """
const findMainLoop = () => {
  if (typeof window.__require !== "function" || typeof cc === "undefined") return null;
  const scene = cc.director.getScene();
  if (!scene) return null;
  const L = window.__require("BattleMainLoop").BattleMainLoop;
  const m = scene.getComponentInChildren(L);
  return m && m._battleUUID && m.frameSync ? m : null;
};
"""

APPLY_SCRIPT = (
    "(scale) => {"
    + _FIND_MAIN_LOOP
    + """
  const m = findMainLoop();
  if (!m) return {applied: false, reason: "no battle"};
  const state = window.__hauntedRoomSpeed;
  if (!state || state.mainLoop !== m || state.battleUUID !== m._battleUUID) {
    window.__hauntedRoomSpeed = {
      mainLoop: m, battleUUID: m._battleUUID, original: m.frameSync.timeScale
    };
  }
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
  const m = findMainLoop();
  const sameBattle = m === state.mainLoop && m._battleUUID === state.battleUUID;
  if (sameBattle) m.setTimeScale(state.original);
  delete window.__hauntedRoomSpeed;
  return {restored: sameBattle, speed: state.original};
}"""
)


async def find_game_frame(page):
    """Return the frame that hosts the Cocos game module loader."""
    for frame in page.frames:
        try:
            if await frame.evaluate(
                "() => typeof window.__require === 'function' && typeof cc !== 'undefined'"
            ):
                return frame
        except Exception:
            continue
    return None


async def apply_battle_speed(frame, scale: float) -> dict:
    """Ensure the live battle has this speed, preserving its original once."""
    return await frame.evaluate(APPLY_SCRIPT, scale)


async def restore_battle_speed(frame) -> dict:
    return await frame.evaluate(RESTORE_SCRIPT)

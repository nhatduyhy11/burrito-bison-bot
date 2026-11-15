"""Temporarily override the live speed of the current battle loop."""

_FIND_MAIN_LOOP = """
const findMainLoop = () => {
  if (typeof window.__require !== "function" || typeof cc === "undefined") return null;
  const scene = cc.director.getScene();
  if (!scene) return null;
  const L = window.__require("BattleMainLoop").BattleMainLoop;
  const m = scene.getComponentInChildren(L);
  return m && m._battleUUID && m.frameSync && typeof m.setTimeScale === "function" ? m : null;
};
"""

APPLY_SCRIPT = (
    "([scale, reapply]) => {"
    + _FIND_MAIN_LOOP
    + """
  const m = findMainLoop();
  if (!m) return {applied: false, reason: "no battle"};
  const state = window.__hauntedRoomSpeed;
  if (reapply && (!state || state.loop !== m || state.uuid !== m._battleUUID)) {
    return {applied: false, reason: "battle changed"};
  }
  const before = m.frameSync.timeScale;
  if (!Number.isFinite(before)) return {applied: false, reason: "battle speed unavailable"};
  if (before !== scale) m.setTimeScale(scale);
  if (!reapply) window.__hauntedRoomSpeed = {loop: m, uuid: m._battleUUID, original: before};
  return {applied: true, before, timeScale: m.frameSync.timeScale};
}"""
)

RESTORE_SCRIPT = (
    "() => {"
    + _FIND_MAIN_LOOP
    + """
  const state = window.__hauntedRoomSpeed;
  if (!state) return {restored: false};
  delete window.__hauntedRoomSpeed;
  const m = findMainLoop();
  if (!m || state.loop !== m || state.uuid !== m._battleUUID) return {restored: false};
  m.setTimeScale(state.original);
  return {restored: true, speed: state.original};
}"""
)


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


async def apply_battle_speed(frame, scale: float, *, reapply: bool = False) -> dict:
    return await frame.evaluate(APPLY_SCRIPT, [scale, reapply])


async def restore_battle_speed(frame) -> dict:
    return await frame.evaluate(RESTORE_SCRIPT)

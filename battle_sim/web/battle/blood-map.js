// Local playtest profile, Đêm Đỏ map (profile.map = { mode: "blood", level }): level = TeamExpandLO
// id (1001-1080 = Ải 1-80, keys of /__sim/dict/blood-dict.json levels). Only on a Đêm Đỏ capture:
// the second account (Guest) and the team flow exist nowhere else. See docs/planning/blood_night_setup.md.
export const BLOOD_BATTLE_TYPES = [47, 48]; // TeamExpedition16 (team), SingleTeamExpedition16 (solo)

export function applyBloodMap(start, { level }, M, step) {
  if (!BLOOD_BATTLE_TYPES.includes(start.battleType)) {
    throw new Error(`Đêm Đỏ needs a Đêm Đỏ capture as base battle (this one is battleType ${start.battleType})`);
  }
  const row = Number.isSafeInteger(level) && M("TeamExpandLO").get(level);
  if (!row || !M("BattleGroundLO").get(row.battleGroundCode)) throw new Error(`Unknown Đêm Đỏ level: ${level}`);
  start.level = level;
  step("blood map", { level, ai: row.showlevel, boss: row.showBoss });
}

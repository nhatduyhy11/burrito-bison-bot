// HeroDermaModule.MAX_PLAN_SKILL_NUM. All three slots accept either skin color.
export const SUMMONER_SLOTS = 3;

export function summonerSkillsConflict(a, b) {
  return a.code === b.code || a.excludes === b.code || b.excludes === a.code;
}

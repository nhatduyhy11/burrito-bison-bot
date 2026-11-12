// HeroDermaModule.MAX_PLAN_SKILL_NUM. All three slots accept either skin color.
export const SUMMONER_SLOTS = 3;

export function summonerSkillsConflict(a, b) {
  return a.code === b.code || a.excludes === b.code || b.excludes === a.code;
}

// Event skins without a skill (e.g. Sanguin Dragoon): stats only, never in a skill slot, so the
// server never sends them in summonerInfos (the client would JSON.parse their empty skill and throw).
export const isPassiveSummonerSkin = (skin) => !skin.skill && !!skin.passiveAttr?.length;

// Profile summonerSkins entries that take one of the SUMMONER_SLOTS skill slots.
export const slottedSkillCount = (entries, skins) => entries.filter(({ name }) => skins[name]?.skill).length;

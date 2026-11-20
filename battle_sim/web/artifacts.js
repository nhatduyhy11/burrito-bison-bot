// Thần Khí (神器, ArtifactLO / ArtifactEntryLO) rules. The client only reads these fields from
// config rows; gen_profile_dict.js checks every row against these formulas so artifact-dict.json
// can store one record per hero instead of 15 variants and 16 copies of the same entry pool.
// See docs/planning/artifact.md.

// Item quality (4 purple, 5 orange, 6 red, 7 gold) -> highest stage.
export const MAX_STAGE = { 4: 3, 5: 3, 6: 4, 7: 5 };
// Entry family -> last two digits of the rainbow (quality 8) skill: 10<NN>07<RR>000.
export const RARE_SKILL = { 1: 7, 2: 6, 3: 8 };

const nn = (heroCode) => String(heroCode % 100).padStart(2, "0");

// hero.pool is the hero's 1-based slot (1..16): item code 1<PP><QQ><SSS>, entry pool PP*100000.
export const artifactCode = (pool, quality, stage) => (100 + pool) * 100000 + quality * 1000 + stage;
export const entryPool = (pool) => pool * 100000;

// ArtifactLO.skillList is cumulative: stage s holds the first s of the hero's five stage skills.
export const stageSkill = (heroCode, k) => Number(`10${nn(heroCode)}070${k}000`);
export const stageSkills = (heroCode, stage) => Array.from({ length: stage }, (_, i) => stageSkill(heroCode, i + 1));

// Rolled slots: one more per stage, starting at quality - 4.
export const holeNum = (quality, stage) => quality - 4 + stage - 1;
export const maxHoleNum = (quality) => holeNum(quality, MAX_STAGE[quality]);

// Entry code <pool><family:5><quality:2>; quality 3..7 are team buffs, 8 the hero's rainbow skills.
export const entryCode = (pool, family, quality) => pool * 10000000 + family * 100 + quality;
export const parseEntryCode = (code) => ({
  pool: Math.floor(code / 10000000), family: Math.floor(code / 100) % 100000, quality: code % 100,
});
export const rareSkill = (heroCode, family) => Number(`10${nn(heroCode)}07${String(RARE_SKILL[family]).padStart(2, "0")}000`);

export const artifactName = (hero, quality, lang = "vn") =>
  quality === 7 ? (lang === "vn" ? hero.name7_vn : hero.name7) : (lang === "vn" ? hero.name_vn : hero.name);

// ---------- Cấp Thần Khí (神器等级, the CommonWeaponLevel battle record) ----------
// The engine reads the record for rainbow eff 07 (family 1: gate "Khi Thần Khí trong trận đạt
// LvN") and eff 08 (family 3: % per level). Nothing writes it mid-battle: the server stamps the
// marker skill 3301000 (武将升神兵打点) into hero.skills at battle load — one entry per level
// (buff overlay_limit 0, duration 1 tick, roster retains). Captures have no stamp, so without
// one the two effs contribute exactly 0% in the sim; the profile's artifact.level injects them
// (web/battle/hero/artifact.js). Cap 0-5 pending a real capture with a level (bbb-b05).
export const WEAPON_LEVEL_MAX = 5;
export const WEAPON_STAMP = 3301000;
// Rainbow skills that scale with the level; family 2 (…0706000) only swaps the Thức Tỉnh card.
export const WEAPON_RAINBOW = /^10\d{2}07(?:07|08)000$/;

// Keyed by the hero's slot nn (heroCode % 100 — the NN in skill ids 10NN07RR000; bundle 7125c
// sea_65553): eff 07 gate level (SkillBuffLO presetParams ["CommonWeaponLevel",1,N]) and the eff
// 08 composition — self +5%/level (Add_Attr_By_Self_Target_Level) and/or team +3.5%/level
// (Halo_Effect_Once_ExcludeSummoner; 31 chains it via 10NN07{08100,08200}).
export const WEAPON_GATE = { 1: 5, 2: 4, 3: 2, 4: 3, 5: 3, 8: 3, 9: 5, 13: 3, 14: 5, 15: 2, 19: 5, 23: 3, 26: 4, 30: 5, 31: 4, 32: 3 };
export const WEAPON_SELF = new Set([1, 2, 8, 9, 13, 14, 15, 19, 31]);
export const WEAPON_TEAM = new Set([3, 4, 5, 23, 26, 30, 31, 32]);
export const weaponGate = (heroCode) => WEAPON_GATE[heroCode % 100];
export const isWeaponSelf = (heroCode) => WEAPON_SELF.has(heroCode % 100);
export const isWeaponTeam = (heroCode) => WEAPON_TEAM.has(heroCode % 100);

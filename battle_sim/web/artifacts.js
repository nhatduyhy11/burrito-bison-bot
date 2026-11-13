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

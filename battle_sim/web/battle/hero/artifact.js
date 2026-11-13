// Local playtest profile, Thần Khí (artifact) of one hero. The battle reads hero.artifact
// {code, battleEntryInfos} itself (ArtifactSkillHub, createAddUnitData, TDBuildVO), so the profile
// only builds that snapshot. hero.attr is left as is: the old item's stats stay in it, like relic.js.
// See docs/planning/artifact.md.
import { MAX_STAGE, artifactCode, holeNum, parseEntryCode } from "../../artifacts.js";

// selection: null = no artifact, { quality, stage, entries: [{ code, value }] } = this item.
export function applyArtifact(hero, selection, M, step) {
  if (selection === null) {
    const { artifact, ...rest } = hero;
    step("profile Thần Khí", { heroCode: hero.code, artifact: null });
    return rest;
  }
  const fail = (msg) => { throw new Error(`Hero ${hero.code} Thần Khí: ${msg}`); };
  const { quality, stage, entries = [] } = selection || {};
  if (!MAX_STAGE[quality]) fail(`phẩm phải là 4-7, nhận ${quality}`);
  if (!Number.isInteger(stage) || stage < 1 || stage > MAX_STAGE[quality]) {
    fail(`stage phải là 1-${MAX_STAGE[quality]} với phẩm ${quality}, nhận ${stage}`);
  }
  const pool = heroPool(hero.code, M) ?? fail("hero không có Thần Khí trong config");
  const code = artifactCode(pool, quality, stage);
  const row = M("ArtifactLO").get(code);
  if (!row || row.hero !== hero.code) fail(`không có món ${code} trong config`);
  if (!Array.isArray(entries) || entries.length > holeNum(quality, stage)) {
    fail(`tối đa ${holeNum(quality, stage)} dòng ở phẩm ${quality} stage ${stage}`);
  }
  const infos = entries.map(({ code: entry, value = 0 }) => {
    const config = M("ArtifactEntryLO").get(entry);
    if (!config || config.entryType !== 2 || parseEntryCode(entry).pool !== pool) {
      fail(`dòng ${entry} không phải buff/skill trong pool của hero`);
    }
    if (!Number.isInteger(value) || value < config.minValue || value > config.maxValue) {
      fail(`dòng ${entry} value phải trong ${config.minValue}-${config.maxValue}, nhận ${value}`);
    }
    if (!M("SkillBaseLO").get(config.skillCode)) fail(`skill ${config.skillCode} của dòng ${entry} không có`);
    return { code: entry, value };
  });
  const artifact = { code, uuid: hero.artifact?.uuid || String(code).padStart(24, "0") };
  if (infos.length) artifact.battleEntryInfos = { ...infos, _length: infos.length };
  step("profile Thần Khí", { heroCode: hero.code, artifact: code, entries: infos });
  return { ...hero, artifact };
}

// Item codes are 1<PP><QQ><SSS> with PP the hero's slot; any ArtifactLO row of the hero gives it.
function heroPool(heroCode, M) {
  const items = M("ArtifactLO");
  for (const key of Object.keys(items.store)) {
    if (/^\d+$/.test(key) && items.get(Number(key))?.hero === heroCode) return Math.floor(Number(key) / 100000) - 100;
  }
  return undefined;
}

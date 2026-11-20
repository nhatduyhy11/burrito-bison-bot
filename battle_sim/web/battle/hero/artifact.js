// Local playtest profile, Thần Khí (artifact) of one hero. The battle reads hero.artifact
// {code, battleEntryInfos} itself (ArtifactSkillHub, createAddUnitData, TDBuildVO), so the profile
// only builds that snapshot. hero.attr is left as is: the old item's stats stay in it, like relic.js.
// See docs/planning/artifact.md.
import { MAX_STAGE, WEAPON_LEVEL_MAX, WEAPON_RAINBOW, WEAPON_STAMP, artifactCode, holeNum, parseEntryCode } from "../../artifacts.js";

// selection: null = no artifact, { quality, stage, entries: [{ code, value }], level? } = this item.
// level = Cấp Thần Khí 0-5: appends that many 3301000 stamps to hero.skills (the only writer of the
// CommonWeaponLevel record the rainbow effs 07/08 read); 0 keeps the captured skills untouched.
export function applyArtifact(hero, selection, rb, M, step) {
  if (selection === null) {
    const { artifact, ...rest } = hero;
    step("profile Thần Khí", { heroCode: hero.code, artifact: null });
    return rest;
  }
  const fail = (msg) => { throw new Error(`Hero ${hero.code} Thần Khí: ${msg}`); };
  const { quality, stage, entries = [], level = 0 } = selection || {};
  if (!MAX_STAGE[quality]) fail(`phẩm phải là 4-7, nhận ${quality}`);
  if (!Number.isInteger(stage) || stage < 1 || stage > MAX_STAGE[quality]) {
    fail(`stage phải là 1-${MAX_STAGE[quality]} với phẩm ${quality}, nhận ${stage}`);
  }
  if (!Number.isInteger(level) || level < 0 || level > WEAPON_LEVEL_MAX) {
    fail(`cấp Thần Khí phải là số 0-${WEAPON_LEVEL_MAX} (cap chờ capture thật xác nhận), nhận ${level}`);
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
  const skills = [...rb.listItems(hero.skills)];
  // Stamp entries: one per level at the end of hero.skills, hidden from the skill bar. Format
  // assumption (bbb-b05): repeated plain entries — no real capture with a stamp exists yet to
  // compare against; revisit via bd append-notes if one shows another shape (e.g. a level field).
  const stamps = Array.from({ length: level }, (_, i) => ({ code: WEAPON_STAMP, index: skills.length + i + 1, isShow: false }));
  if (stamps.length) step("profile Cấp Thần Khí", { heroCode: hero.code, level, stamps: WEAPON_STAMP });
  return { ...hero, artifact, skills: stamps.length ? [...skills, ...stamps] : hero.skills };
}

// A hero carrying rainbow eff 07/08 without any stamp runs them at exactly 0% — the record they
// read is lobby progress the capture never had. Warn (once per built hero) instead of faking it;
// setting Cấp Thần Khí in the profile injects the stamps.
export function warnMissingStamps(hero, rb) {
  const skills = rb.listItems(hero.skills);
  if (skills.some(({ code }) => WEAPON_RAINBOW.test(String(code)))
    && !skills.some(({ code }) => code === WEAPON_STAMP)) {
    console.warn(`[sim] Hero ${hero.code}: skill cầu vồng 07/08 có trong trận nhưng không có dấu ${WEAPON_STAMP}`
      + " — đang đóng góp 0%; đặt Cấp Thần Khí trong setup để đóng dấu (bbb-b05)");
  }
}

// Item codes are 1<PP><QQ><SSS> with PP the hero's slot; any ArtifactLO row of the hero gives it.
function heroPool(heroCode, M) {
  const items = M("ArtifactLO");
  for (const key of Object.keys(items.store)) {
    if (/^\d+$/.test(key) && items.get(Number(key))?.hero === heroCode) return Math.floor(Number(key) / 100000) - 100;
  }
  return undefined;
}

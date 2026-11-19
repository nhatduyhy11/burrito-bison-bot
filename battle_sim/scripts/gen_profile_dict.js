"use strict";
// Generate the playtest catalogs from the game's own config tables:
// - web/dict/map-dict.json: what can be played: campaign stage range, capital (U Đô) battleType + boss ids;
// - web/dict/boss-dict.json: capital bosses with their preset variants (the 3 companion creeps, by id);
// - web/dict/creeps-dict.json: the companion creeps the boss presets reference, deduped;
// - web/dict/blood-dict.json: Blood Night (battleType 47) levels with their boss, mini bosses and creeps in one dict;
// - web/dict/antique-dict.json: antiques with setup labels and battle rank codes;
// - web/dict/relic-dict.json: Thánh Khí (relics) by line and purification step, with their skills;
// - web/dict/artifact-dict.json: Thần Khí per hero (names, slot) + shared team buffs; rules in web/artifacts.js;
// - web/dict/hero-dict.json: the hero side: heroes with their skins and Dị Năng (avatar) nodes;
// - web/dict/support-dict.json: the non-hero side: Summoner skins, traps, pets, spells (daoists),
//   Summoner gear skills, building skins, mounts and mount privilege types.
// Entries are keyed by a slug of the English name. `name` / `name_vn` come from the game's language packs (lang_en /
// lang_vi.<ver>.bin, public CDN next to config.bin; downloaded once into
// .tmp/battle_sim/config/<configVersion>/). Skill refs that feed the hover popovers also carry
// `desc_vn` (lang_vi desc, en desc as fallback).
//
//   node battle_sim/scripts/gen_profile_dict.js [configVersion] [battleVersion]
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");
const { Sim } = require("../lib/sim");
const versions = require("../lib/versions");

const CONFIG_VERSION = process.argv[2] || "sea_65553";
const BATTLE_VERSION = process.argv[3] || "2.3.1-2_E64067_P63528_C64067";
const ASSETS = { battleVersion: BATTLE_VERSION, configVersion: CONFIG_VERSION, mapVersion: "trunk_61543" };
const HERO_OUT = path.join(__dirname, "..", "web", "dict", "hero-dict.json");
const SUPPORT_OUT = path.join(__dirname, "..", "web", "dict", "support-dict.json");
const MAP_OUT = path.join(__dirname, "..", "web", "dict", "map-dict.json");
const BOSS_OUT = path.join(__dirname, "..", "web", "dict", "boss-dict.json");
const CREEPS_OUT = path.join(__dirname, "..", "web", "dict", "creeps-dict.json");
const CAMPAIGN_OUT = path.join(__dirname, "..", "web", "dict", "campaign-dict.json");
const BLOOD_OUT = path.join(__dirname, "..", "web", "dict", "blood-dict.json");
const ANTIQUE_OUT =path.join(__dirname, "..", "web", "dict", "antique-dict.json");
const RELIC_OUT = path.join(__dirname, "..", "web", "dict", "relic-dict.json");
const ARTIFACT_OUT = path.join(__dirname, "..", "web", "dict", "artifact-dict.json");
const BUILDINGS = { door: 1, bed: 2, generator: 3, cat: 4 }; // EBuildType: Door, Bed, WoodenFish, GoldenToad
const SKIN_COLOR = { 4: "default", 6: "red", 7: "gold", 8: "colorful" };
// Rarity = card border in game (HeroLO / OrganLO / SummonCreatureLO .color). Spells have no rarity tiers.
const RARITY = { 3: "blue", 4: "purple", 5: "orange", 6: "red", 7: "gold" };
const BUILD_SLOT = { 0: "none", 1: "red", 2: "gold", 3: "special" };

const slug = (s) => String(s).toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
function keyed(entries) { // [[name, value]] -> {slug: value}, codes appended on collisions
  const out = {};
  for (const [name, value] of entries) {
    // No English name in lang_en (e.g. unreleased skins keep the Chinese name): key by code.
    let key = slug(name) || `id_${value.skinId ?? value.code}`;
    if (Object.hasOwn(out, key)) key += "_" + (value.code ?? value.skinId);
    out[key] = value;
  }
  return out;
}
const rows = (lo) => { const list = []; lo.store.foreach((_k, v) => list.push(v)); return list; };
const jsonField = (value) => value ? JSON.parse(value) : [];
function maxBy(lo, field) { // mecType -> max of field
  const max = new Map();
  for (const r of rows(lo)) max.set(r.mecType, Math.max(max.get(r.mecType) || 0, r[field]));
  return max;
}
// simpleDesc cleanup: <br> becomes the " · " segment separator the popovers split on and rich-text
// tags go. The lang packs sometimes keep a stray hex tail right after an opening color tag
// (e.g. "<color=#FF6347>ff>Trống</c>" — ship data, not our parse), so drop that with the tag too.
const strip = (s) => String(s || "").replace(/<br\s*\/?>/gi, " · ").replace(/(<color[^>]*>)[0-9a-fA-F]{2,8}>/gi, "$1")
  .replace(/<[^>]+>/g, "").replace(/\s+/g, " ").replace(/\s*·\s*/g, " · ").trim();

async function main() {
  const assets = await versions.resolveAssets(ASSETS);
  // One loader per language: *LO names are translated while rows parse, so the language
  // pack is loaded before any table is read, and each loader keeps its own tables.
  async function tablesIn(lang) {
    const langFile = await versions.ensureLanguage(CONFIG_VERSION, lang);
    const req = new Sim(assets).req;
    const reader = new (req("BinaryReader").BinaryReader)();
    reader.init(req("QuickLZ").QuickLZ.decompress(new Uint8Array(fs.readFileSync(langFile))));
    if (!new (req("LangParser").LangParser)().writeBinaryDataImmediately(reader)) throw new Error(`${lang} pack failed`);
    return (n) => req(n)[n];
  }
  const M = await tablesIn("en");
  const V = await tablesIn("vi");
  const vn = (table, key) => V(table).get(key)?.name;
  const SkillBase = M("SkillBaseLO");
  // Hover-popover skill data: desc prefers lang_vi (the pack the game itself loads), the en desc is
  // the fallback. `starSkillsOf` folds per-star rows into relic-style runs: consecutive stars with
  // an identical payload become one {stars, ...payload} entry.
  const skillRef = (code) => ({ code, name: SkillBase.get(code)?.name, name_vn: vn("SkillBaseLO", code),
    desc_vn: V("SkillBaseLO").get(code)?.desc?.trim() || SkillBase.get(code)?.desc?.trim() });
  const starSkillsOf = (list) => { // [[star, payload]] -> [{stars, ...payload}]
    const out = [];
    for (const [star, payload] of [...list].sort((a, b) => a[0] - b[0])) {
      const last = out.at(-1);
      if (last) { const { stars, ...rest } = last;
        if (JSON.stringify(rest) === JSON.stringify(payload)) { last.stars.push(star); continue; } }
      out.push({ stars: [star], ...payload });
    }
    return out;
  };

  // Hero and Summoner skins share DermaLO and DermaStarLO.
  const dermaMaxStar = new Map();
  for (const r of rows(M("DermaStarLO"))) dermaMaxStar.set(r.dermaCode, Math.max(dermaMaxStar.get(r.dermaCode) || 0, r.star));
  // Per-star skin skill (DermaStarLO._skill, one SkillBaseLO code per star): popover data for hero
  // and Summoner skins.
  const dermaStarSkills = new Map();
  for (const r of rows(M("DermaStarLO"))) {
    if (!r.skill) continue;
    const list = dermaStarSkills.get(r.dermaCode) || [];
    list.push([r.star, skillRef(jsonField(r.skill)[0])]);
    dermaStarSkills.set(r.dermaCode, list);
  }
  const dermas = rows(M("DermaLO"));
  const heroSkins = dermas.filter((d) => d.dermatype === 1);
  const isEventReward = (row) => ["活动获得", "Obtained from events."].includes(row.sourceName);
  const eventUnlock = (row, costs) => ({
    source: row.sourceName,
    unlockCosts: jsonField(costs),
  });
  const summonerSkins = keyed(dermas.filter((d) => d.dermatype === 2).sort((a, b) => a.code - b.code).map((d) => [d.name, {
    code: d.code, name: d.name, name_vn: vn("DermaLO", d.code), color: SKIN_COLOR[d.color] || d.color,
    maxStar: dermaMaxStar.get(d.code) || 1, model: d.deco,
    ...(d.skills?.length ? { skill: SkillBase.get(d.skills.get(0))?.name, skill_vn: vn("SkillBaseLO", d.skills.get(0)) } : {}),
    ...(dermaStarSkills.has(d.code) ? { starSkills: starSkillsOf(dermaStarSkills.get(d.code)) } : {}),
    ...(!d.skills?.length && isEventReward(d) && d.hideStar ? {
      ...eventUnlock(d, d.costs),
      passiveAttr: jsonField(M("DermaStarLO").get(d.code * 100 + 1)?.attr),
    } : {}),
    ...(d.exclusion ? { excludes: d.exclusion } : {}),
  }]));

  // Dị Năng (异能) skill nodes per hero subType: AvatarUpGradeLO rows with a skillcode, one per
  // chapter 1-5, in chapter order (level N = the first N). Each swaps `replaces` for `skill` in
  // hero.skills (adds it when replaces is null); the server builds hero.skills exactly by this rule.
  // `skillUnlock` = [heroId, breakthrough]: the node only applies from that breakthrough on (the
  // SkillReplaceLO level of the skill it replaces); the client never reads it, the server does.
  // `skillInfo` / `replacesInfo` carry name + desc for the hover popover. Attribute nodes are left
  // out (server-side attr, not modelled). See docs/planning/hero_gear.md.
  const avatarRows = new Map();
  for (const row of rows(M("AvatarUpGradeLO"))) {
    if (!row.skillcode) continue;
    const point = M("AvatarLO").get(row.pointCode);
    const list = avatarRows.get(point.subType) || [];
    const minBreakThrough = jsonField(row.skillUnlock)[1];
    list.push({ chapter: point.chapter, node: { replaces: row.oldSkillCode || null, skill: row.skillcode,
      skillInfo: skillRef(row.skillcode),
      ...(row.oldSkillCode ? { replacesInfo: skillRef(row.oldSkillCode) } : {}),
      ...(minBreakThrough ? { minBreakThrough } : {}) } });
    avatarRows.set(point.subType, list);
  }
  const avatarNodes = new Map([...avatarRows].map(([subType, list]) =>
    [subType, list.sort((a, b) => a.chapter - b.chapter).map(({ node }) => node)]));

  // Heroes: base skills 10<NN><slot><lv=01>000 for slots 1-3.
  const heroes = keyed(rows(M("HeroLO")).filter((h) => h.isShow).sort((a, b) => a.code - b.code).map((h) => {
    const nn = String(h.code % 1000).padStart(2, "0");
    const baseSkills = [1, 2, 3].map((slot) => Number(`10${nn}0${slot}01000`)).filter((id) => SkillBase.get(id));
    // DermaLO.heroCode holds HeroLO.subType (DermaStarLO.heroCode holds the hero code).
    const own = heroSkins.filter((d) => d.heroCode === h.subType).sort((a, b) => a.index - b.index || a.code - b.code);
    const skinKey = new Map(Object.entries(keyed(own.map((d) => [d.name, d]))).map(([k, d]) => [d.code, k]));
    const skins = {};
    for (const d of own) {
      const requires = JSON.parse(d.requirement || "[]").map(([code]) => skinKey.get(code));
      skins[skinKey.get(d.code)] = {
        code: d.code, name: d.name, name_vn: vn("DermaLO", d.code), color: SKIN_COLOR[d.color] || d.color, maxStar: dermaMaxStar.get(d.code) || 1,
        ...(dermaStarSkills.has(d.code) ? { starSkills: starSkillsOf(dermaStarSkills.get(d.code)) } : {}),
        ...(requires.length ? { requires } : {}),
      };
    }
    return [h.name, { code: h.code, name: h.name, name_vn: vn("HeroLO", h.code), color: RARITY[h.color] || h.color, baseSkills,
      ...(own.length ? { skins } : {}), ...(avatarNodes.has(h.subType) ? { avatarNodes: avatarNodes.get(h.subType) } : {}) }];
  }));

  const organLevel = maxBy(M("OrganUpGradeLO"), "level"), organStar = maxBy(M("OrganStarLO"), "star");
  // Per-star trap skill (OrganStarLO._skillCode); repalceSkillCodes (sic) lists the variants this
  // star swaps out (Phantom Mirror stars 7-10 swap in a ...X100 variant).
  const organStarSkills = new Map();
  for (const r of rows(M("OrganStarLO"))) {
    if (!r.skillCode) continue;
    const replaces = jsonField(r.repalceSkillCodes);
    const list = organStarSkills.get(r.mecType) || [];
    list.push([r.star, { ...skillRef(r.skillCode), ...(replaces.length ? { replaces } : {}) }]);
    organStarSkills.set(r.mecType, list);
  }
  // A selectable trap needs its unlock items and the tags the battle UI renders.
  const availableTrap = (organ) =>
    jsonField(organ.cost).every(([type, item]) => type !== 3 || M("ItemLO").get(item)) &&
    jsonField(organ.tag).every((tag) => M("HeroTagLO").get(tag));
  const traps = keyed(rows(M("OrganLO")).filter(availableTrap).sort((a, b) => a.code - b.code).map((o) => [o.name,
    { code: o.code, name: o.name, name_vn: vn("OrganLO", o.code), color: RARITY[o.color] || o.color,
      maxLevel: organLevel.get(o.mecType) || 1, maxStar: organStar.get(o.mecType) || 1,
      ...(organStarSkills.has(o.mecType) ? { starSkills: starSkillsOf(organStarSkills.get(o.mecType)) } : {}) }]));

  const petLevel = maxBy(M("SummonCreatureUpGradeLO"), "level"), petStar = maxBy(M("SummonCreatureStarLO"), "star");
  // Pet battle skills: SummonCreatureLO._skill holds SummonCreatureSkillLO._type group codes (not
  // SkillBaseLO codes — why pets looked skill-less); each group is one battle skill whose levels
  // unlock by star (_starRequire), one SkillBaseLO code per level.
  const petSkillGroups = new Map();
  for (const r of rows(M("SummonCreatureSkillLO"))) {
    const list = petSkillGroups.get(r.type) || [];
    list.push([r.starRequire, skillRef(r.skillCode)]);
    petSkillGroups.set(r.type, list);
  }
  const pets = keyed(rows(M("SummonCreatureLO")).sort((a, b) => a.code - b.code).map((p) => {
    const groups = jsonField(p.skill).filter((t) => petSkillGroups.has(t))
      .map((t) => ({ type: t, starSkills: starSkillsOf(petSkillGroups.get(t)) }));
    return [p.name, { code: p.code, name: p.name, name_vn: vn("SummonCreatureLO", p.code), color: RARITY[p.color] || p.color,
      maxLevel: petLevel.get(p.mecType) || 1, maxStar: petStar.get(p.mecType) || 1,
      ...(groups.length ? { skills: groups } : {}) }];
  }));

  const spellStar = maxBy(M("DaoistStarLO"), "star");
  // Per-star spell skill (DaoistStarLO._skillCode) with the cast params the popover shows.
  const spellStarSkills = new Map();
  for (const r of rows(M("DaoistStarLO"))) {
    if (!r.skillCode) continue;
    const list = spellStarSkills.get(r.mecType) || [];
    list.push([r.star, { ...skillRef(r.skillCode), cd: r.skillCd, range: r.ranges }]);
    spellStarSkills.set(r.mecType, list);
  }
  const spells = keyed(rows(M("DaoistLO")).sort((a, b) => a.code - b.code).map((d) => [d.name,
    { code: d.code, name: d.name, name_vn: vn("DaoistLO", d.code), maxStar: spellStar.get(d.mecType) || 1,
      ...(spellStarSkills.has(d.mecType) ? { starSkills: starSkillsOf(spellStarSkills.get(d.mecType)) } : {}) }]));

  // Building skins: BuildSkinLO rows are per star (code = skinId * 100 + star).
  const buildSkins = new Map();
  for (const r of rows(M("BuildSkinLO"))) {
    const prev = buildSkins.get(r.skinId);
    if (!prev || r.star > prev.maxStar) buildSkins.set(r.skinId, { row: prev?.row?.star === 1 ? prev.row : r, maxStar: r.star });
    if (r.star === 1) buildSkins.get(r.skinId).row = r;
  }
  // Per-star building-skin skill (BuildSkinLO._skill).
  const buildStarSkills = new Map();
  for (const r of rows(M("BuildSkinLO"))) {
    if (!r.skill) continue;
    const list = buildStarSkills.get(r.skinId) || [];
    list.push([r.star, skillRef(jsonField(r.skill)[0])]);
    buildStarSkills.set(r.skinId, list);
  }
  const buildings = {};
  for (const [id, buildType] of Object.entries(BUILDINGS)) {
    const own = [...buildSkins.values()].filter(({ row }) => row.buildType === buildType)
      .sort((a, b) => a.row.skinId - b.row.skinId);
    const skinKey = new Map(Object.entries(keyed(own.map(({ row }) => [row.name, row]))).map(([k, r]) => [r.skinId, k]));
    const skins = {};
    for (const { row, maxStar } of own) {
      const requires = JSON.parse(row.requirement || "[]").map(([skinId]) => skinKey.get(skinId));
      skins[skinKey.get(row.skinId)] = {
        skinId: row.skinId, name: row.name, name_vn: vn("BuildSkinLO", row.code), color: SKIN_COLOR[row.color] || row.color,
        slot: BUILD_SLOT[row.skillType] ?? row.skillType, maxStar,
        ...(buildStarSkills.has(row.skinId) ? { starSkills: starSkillsOf(buildStarSkills.get(row.skinId)) } : {}),
        ...(row.isInit ? { default: true } : {}), ...(requires.length ? { requires } : {}),
        ...(row.skillType === 3 && isEventReward(row) && row.hideStar ? {
          ...eventUnlock(row, row.cost1), skillCodes: jsonField(row.skill),
        } : {}),
      };
    }
    buildings[id] = { buildType, skins };
  }

  // Campaign stages: AdventuretdLevelLO id = stage * 10, with a BattleGround (same check as profile.js).
  const stages = rows(M("AdventuretdLevelLO")).map((r) => r.id / 10)
    .filter((stage) => Number.isInteger(stage) && M("BattleGroundLO").get(M("AdventuretdLevelLO").get(stage * 10).battleGroundCode))
    .sort((a, b) => a - b);
  const capital = capitalCatalogs(M, V);
  const campaign = campaignCatalogs(M, V);
  const blood = bloodNightCatalogs(M, V);
  const maps = { campaign: { minStage: stages[0], maxStage: stages[stages.length - 1], stages: stages.length },
    capital: { battleType: capital.battleType, bosses: Object.keys(capital.bosses) } };

  const mountRanks = rows(M("MountStarLO"));
  const mounts = keyed(rows(M("MountLO")).map((mount) => [mount.name, {
    code: mount.id, name: mount.name, name_vn: vn("MountLO", mount.id),
    color: RARITY[mount.color] ?? mount.color,
    ...(mount.displayA ? { frontModel: mount.displayA } : {}),
    backModel: mount.displayB, hiddenUntilOwned: !!mount.bHideCond,
    ranks: mountRanks.filter((rank) => rank.mecType === mount.id).sort((a, b) => a.star - b.star).map((rank) => ({
      code: rank.code, star: rank.star, attr: Object.fromEntries(jsonField(rank.attr)),
      privileges: jsonField(rank.privilege),
      ...(rank.showSkill ? { showSkill: skillRef(rank.showSkill) } : {}),
    })),
  }]));
  const mountPrivilegeTypes = { 1: "MoveSpeed", 2: "PassWall", 3: "GVGEnergy", 4: "GVGShow" };

  // Summoner gear (EquipmentLO, 6 slots): the only battle skills are EquipmentEntryLO rows with a
  // skillCode (one "unique" entry per piece type). EquipmentLO code = 60 P SS QQ (P = piece type,
  // SS = tier/stage); a piece rolls entries from its _entryPool. In StartGameP these skills sit on
  // builds[type 2].skills. Stats are left out (server merges them). See docs/planning/hero_gear.md.
  const entrySkill = new Map(rows(M("EquipmentEntryLO")).filter((e) => e.skillCode).map((e) => [e.entryPool, e.skillCode]));
  const gearSkillPieces = new Map();
  for (const eq of rows(M("EquipmentLO"))) {
    const code = entrySkill.get(eq.entryPool);
    if (!code) continue;
    const list = gearSkillPieces.get(code) || [];
    list.push(eq);
    gearSkillPieces.set(code, list);
  }
  const summonerGear = keyed([...gearSkillPieces].sort(([a], [b]) => a - b).map(([code, pieces]) => {
    const pieceTypes = new Set(pieces.map((p) => Math.floor(p.code / 1e5) % 10));
    if (pieceTypes.size !== 1) throw new Error(`gear skill ${code}: on several piece types`);
    const first = pieces.reduce((a, b) => (b.stage < a.stage || (b.stage === a.stage && b.quality < a.quality) ? b : a));
    const stages = pieces.map((p) => p.stage);
    return [SkillBase.get(code)?.name, { ...skillRef(code), piece: [...pieceTypes][0],
      example: { code: first.code, name: first.name, name_vn: vn("EquipmentLO", first.code) },
      minStage: Math.min(...stages), maxStage: Math.max(...stages),
      qualities: [...new Set(pieces.map((p) => p.quality))].sort((a, b) => a - b) }];
  }));

  // The engine looks up effects and level limits in AntiqueHaloLO by rank code.
  const haloRows = rows(M("AntiqueHaloLO"));
  // Per-star halo skill (AntiqueHaloLO._skillCode; 5 antiques have none). The desc is the one the
  // in-game antique detail view shows (AntiqueDetailView reads AntiqueHaloShowLO.text, rows only at
  // the tier stars 1/4/8/12/15), not the SkillBaseLO desc: those differ, e.g. Càn Long's skill desc
  // says "ST mà Anh Hùng…" while the game shows the hero-skin-star scaling. The live "(Hiện tại +X%)"
  // suffix needs the account's haloLevel and is left out.
  const haloShowText = (antiqueCode, star) => {
    const show = rows(V("AntiqueHaloShowLO")).filter((s) => s.antiqueCode === antiqueCode && s.star <= star && s.text)
      .sort((a, b) => b.star - a.star)[0];
    return show?.text?.trim();
  };
  const haloStarSkills = new Map();
  for (const r of haloRows) {
    if (!r.skillCode) continue;
    const list = haloStarSkills.get(r.antiqueCode) || [];
    const ref = skillRef(r.skillCode);
    list.push([r.star, { ...ref, desc_vn: haloShowText(r.antiqueCode, r.star) || ref.desc_vn }]);
    haloStarSkills.set(r.antiqueCode, list);
  }
  const antiques = keyed(rows(M("AntiqueLO")).map((row) => {
    const haloRanks = haloRows.filter((halo) => halo.antiqueCode === row.code)
      .sort((a, b) => a.star - b.star);
    const ranks = haloRanks.map(({ code, star }, index) => {
      if (star !== index + 1) throw new Error(`Antique ${row.code}: expected star ${index + 1}, got ${star}`);
      return code;
    });
    return [row.name, {
      code: row.code, name: row.name, name_vn: vn("AntiqueLO", row.code),
      color: RARITY[row.color] ?? row.color, maxStar: ranks.length, ranks,
      ...(haloStarSkills.has(row.code) ? { starSkills: starSkillsOf(haloStarSkills.get(row.code)) } : {}),
    }];
  }));

  // Thánh Khí (圣器, RelicLO type 2). Quality 6-8 relics come in 7 lines (code 82QQLL01, LL = line):
  // red (Q=06) -> gold (07) -> colorful (08), each step a purification (thanh tẩy, RelicQualityUpLO,
  // star kept). Per line: one star-tier skill (same codes at every purification) and, from gold
  // on, one fixed skill. Quality 1-5 relics (no skill) are left out. Stats are left out: they reach battle
  // already merged into hero.attr by the server, the client computes none; see docs/planning/hero_gear.md.
  const RELIC_COLOR = { ...RARITY, 8: "colorful" };
  const relicStars = rows(M("RelicStarLO"));
  const relicFields = (r) => ({ code: r.code, quality: r.quality, color: RELIC_COLOR[r.quality] ?? r.quality,
    name: r.name, name_vn: vn("RelicLO", r.code) });
  const thanhKhi = rows(M("RelicLO")).filter((r) => r.type === 2).sort((a, b) => a.code - b.code);
  const relicLines = keyed(thanhKhi.filter((r) => r.quality === 6).map((red) => {
    const line = Math.floor(red.code / 100) % 100;
    const tiers = [6, 7, 8].map((q) => M("RelicLO").get(82000001 + q * 10000 + line * 100)).filter(Boolean);
    const starRows = (r) => relicStars.filter((s) => s.code === r.code).sort((a, b) => a.star - b.star);
    const tierSkill = (s) => jsonField(s.skill).find((c) => Math.floor(c / 1e7) === 5206);
    const starSkills = [];
    for (const s of starRows(red)) {
      const last = starSkills.at(-1);
      if (last?.code === tierSkill(s)) last.stars.push(s.star); else starSkills.push({ stars: [s.star], ...skillRef(tierSkill(s)) });
    }
    return [red.name, { line, name: red.name, name_vn: vn("RelicLO", red.code), starSkills, purifications: tiers.map((r, times) => {
      const stars = starRows(r);
      if (stars.some((s, i) => tierSkill(s) !== tierSkill(starRows(red)[i]))) throw new Error(`relic ${r.code}: star skills differ from red`);
      const fixed = jsonField(stars[0].skill).find((c) => Math.floor(c / 1e7) !== 5206);
      return { times, ...relicFields(r), ...(fixed ? { fixedSkill: skillRef(fixed) } : {}), maxStar: stars.at(-1)?.star };
    }) }];
  }));
  const purifyItem = Number(jsonField(rows(M("RelicQualityUpLO"))[0].cost)[0][1]);
  const relicConst = (name) => M("ConstLO").get(name)?.constValue;
  const relics = {
    purification: {
      maxTimes: 2, steps: [{ from: "red", to: "gold" }, { from: "gold", to: "colorful", needsGoldRelics: Number(relicConst("relicAgainImproveColorRequite")) }],
      item: { code: purifyItem, name: M("ItemLO").get(purifyItem)?.name, name_vn: vn("ItemLO", purifyItem), desc_vn: V("ItemLO").get(purifyItem)?.desc },
    },
    lines: relicLines,
  };

  // Thần Khí (神器). Item code, stage skills, holes and entry codes follow web/artifacts.js; every
  // config row is checked against it, so the dict keeps one record per hero and one shared buff
  // table. Stats (ArtifactLO.attr, entryType 1) are left out: the battle gets them in hero.attr.
  const A = await import(pathToFileURL(path.join(__dirname, "..", "web", "artifacts.js")).href);
  const expect = (ok, what) => { if (!ok) throw new Error(`artifact rule broken: ${what}`); };
  const artifactRows = rows(M("ArtifactLO")).sort((a, b) => a.code - b.code);
  const artifactHeroes = {};
  const artifactSkillCodes = new Set();
  const poolHero = new Map();
  for (const row of artifactRows) {
    const pool = row.entryPool / 100000;
    const hero = artifactHeroes[row.hero] ??= { pool, variants: 0 };
    poolHero.set(row.entryPool, row.hero);
    const name = row.quality === 7 ? "name7" : "name";
    const nameVn = vn("ArtifactLO", row.code);
    expect((hero[name] ??= row.name) === row.name && (hero[`${name}_vn`] ??= nameVn) === nameVn, `${row.code} name`);
    expect(hero.pool === pool && row.code === A.artifactCode(pool, row.quality, row.stage), `${row.code} code/pool`);
    expect(row.stage >= 1 && row.stage <= A.MAX_STAGE[row.quality], `${row.code} stage`);
    expect(JSON.stringify(jsonField(row.skillList)) === JSON.stringify(A.stageSkills(row.hero, row.stage)), `${row.code} skillList`);
    expect(row.holeNum === A.holeNum(row.quality, row.stage) && row.maxHoleNum === A.maxHoleNum(row.quality), `${row.code} holes`);
    hero.variants++;
  }
  for (const [code, hero] of Object.entries(artifactHeroes)) {
    const total = Object.values(A.MAX_STAGE).reduce((a, b) => a + b, 0);
    expect(hero.variants === total && hero.name !== hero.name7, `${code} variants/names`);
    delete hero.variants;
    A.stageSkills(Number(code), 5).forEach((skill) => artifactSkillCodes.add(skill));
  }
  // Team buffs (quality 3-7) are identical in every pool apart from the pool prefix of the code.
  const buffs = {};
  for (const row of rows(M("ArtifactEntryLO")).sort((a, b) => a.code - b.code)) {
    const heroCode = poolHero.get(row.entryPool);
    if (!heroCode || row.entryType !== 2 || !row.skillCode) continue;
    const { pool, family, quality } = A.parseEntryCode(row.code);
    expect(pool * 100000 === row.entryPool && quality === row.quality, `entry ${row.code} code`);
    artifactSkillCodes.add(row.skillCode);
    if (quality === 8) {
      expect(row.skillCode === A.rareSkill(heroCode, family) && !row.minValue && !row.maxValue, `entry ${row.code} rare`);
      continue;
    }
    const buff = buffs[family] ??= { skillCode: row.skillCode, percent: row.percent, ranges: {} };
    const range = [row.minValue, row.maxValue];
    expect(buff.skillCode === row.skillCode && buff.percent === row.percent, `entry ${row.code} family`);
    expect(JSON.stringify(buff.ranges[quality] ??= range) === JSON.stringify(range), `entry ${row.code} range`);
  }
  const rareCount = rows(M("ArtifactEntryLO")).filter((r) => poolHero.has(r.entryPool) && r.entryType === 2 && r.quality === 8).length;
  expect(rareCount === poolHero.size * Object.keys(A.RARE_SKILL).length, "rainbow entries per pool");
  const artifactSkills = Object.fromEntries([...artifactSkillCodes].sort((a, b) => a - b).map((code) => {
    if (!SkillBase.get(code)) throw new Error(`artifact skill ${code} missing from SkillBaseLO`);
    return [code, skillRef(code)];
  }));

  const stamp = `node battle_sim/scripts/gen_profile_dict.js ${CONFIG_VERSION} (names: lang_en, vi: lang_vi, desc fallback: lang_en)`;
  const write = (file, data) => fs.writeFileSync(file, JSON.stringify({ _generated: stamp, ...data }, null, 2) + "\n");
  write(HERO_OUT, { heroes });
  write(SUPPORT_OUT, { summonerSkins, summonerGear, traps, pets, spells, buildings, mounts, mountPrivilegeTypes });
  write(MAP_OUT, maps);
  write(BOSS_OUT, { bosses: capital.bosses });
  write(CAMPAIGN_OUT, { stages: campaign.stages });
  write(CREEPS_OUT, { creeps: capital.creeps, campaign: campaign.creeps });
  write(BLOOD_OUT, blood);
  write(ANTIQUE_OUT, { antiques });
  write(RELIC_OUT, relics);
  write(ARTIFACT_OUT, { heroes: artifactHeroes, buffs, skills: artifactSkills });
  const count = (o) => Object.keys(o).length;
  console.log(`wrote ${path.relative(process.cwd(), ARTIFACT_OUT)}: ${count(artifactHeroes)} heroes (${artifactRows.length} variants checked), ` +
    `${count(buffs)} team buffs, ${rareCount} rainbow entries checked`);
  console.log(`wrote ${path.relative(process.cwd(), RELIC_OUT)}: ${count(relics.lines)} relic lines`);
  console.log(`wrote ${path.relative(process.cwd(), MAP_OUT)}: campaign stages ${maps.campaign.minStage}-${maps.campaign.maxStage}, ` +
    `${maps.capital.bosses.length} capital boss ids`);
  console.log(`wrote ${path.relative(process.cwd(), BOSS_OUT)}: ${count(capital.bosses)} capital bosses, ` +
    `${Object.values(capital.bosses).reduce((n, b) => n + b.presets.length, 0)} presets`);
  console.log(`wrote ${path.relative(process.cwd(), CREEPS_OUT)}: ${count(capital.creeps)} creeps, ${count(campaign.creeps)} campaign creeps`);
  console.log(`wrote ${path.relative(process.cwd(), CAMPAIGN_OUT)}: ${count(campaign.stages)} campaign stages`);
  const kinds = Object.values(blood.monsters).reduce((n, m) => ({ ...n, [m.kind]: (n[m.kind] || 0) + 1 }), {});
  console.log(`wrote ${path.relative(process.cwd(), BLOOD_OUT)}: ${count(blood.levels)} Blood Night levels, ` +
    Object.entries(kinds).map(([k, n]) => `${n} ${k}`).join(", "));
  console.log(`wrote ${path.relative(process.cwd(), ANTIQUE_OUT)}: ${count(antiques)} antiques`);
  console.log(`wrote ${path.relative(process.cwd(), HERO_OUT)}: ${count(heroes)} heroes`);
  console.log(`wrote ${path.relative(process.cwd(), SUPPORT_OUT)}: ${count(traps)} traps, ` +
    `${count(pets)} pets, ${count(spells)} spells, ${count(summonerSkins)} Summoner skins, ` +
    `${count(mounts)} mounts, ${count(summonerGear)} Summoner gear skills, ` +
    Object.entries(buildings).map(([k, b]) => `${k} ${count(b.skins)} skins`).join(", "));
}

// Capital (U Đô, GuildNavalWar, battleType 21). Battle level = day*10000 + pos*100 + index and the
// game reads GuildNavalWarLO.get(day*10000 + pos*100): index is ignored, and every row has the
// same creep stat levels, so a room's size never changes the battle. A row only picks the boss and
// its 3 creep types (showCreep = [boss, creepA, creepB, creepC]; the round list follows from it).
// Rows with the same showCreep play the same battle, so each is one preset (level = the first row
// it appears on, +1; the other rows differ only in day/room). See battle_sim/docs/planning/capital.md.
// Split into three catalogs: map-dict.json keeps the map and the boss ids, boss-dict.json the boss
// records with their presets (creeps referenced by id), creeps-dict.json the deduped creeps.
function capitalCatalogs(M, V) {
  const creep = (code) => {
    const row = M("CreepLO").get(code);
    return { code, name: row.name, name_vn: V("CreepLO").get(code)?.name };
  };
  const bosses = new Map();
  for (const row of rows(M("GuildNavalWarLO")).sort((a, b) => a.id - b.id)) {
    const [bossCode, ...creepCodes] = JSON.parse(row.showCreep);
    if (!bosses.has(bossCode)) bosses.set(bossCode, new Map());
    const presets = bosses.get(bossCode);
    if (!presets.has(row.showCreep)) presets.set(row.showCreep, { level: row.id + 1, creeps: creepCodes });
  }
  // Companion creeps, deduped across every boss preset (bosses themselves live in boss-dict.json).
  const creepCodes = [...new Set([...bosses.values()].flatMap((presets) => [...presets.values()].flatMap((p) => p.creeps)))].sort((a, b) => a - b);
  const creeps = keyed(creepCodes.map((code) => [creep(code).name, creep(code)]));
  const creepKey = new Map(Object.entries(creeps).map(([key, c]) => [c.code, key]));
  const list = [...bosses].sort(([a], [b]) => a - b).map(([code, presets]) => {
    const row = M("CreepLO").get(code);
    const vi = V("CreepLO").get(code);
    return [row.name, {
      ...creep(code), avatar: row.avatar, desc: strip(row.simpleDesc), desc_vn: strip(vi?.simpleDesc),
      presets: [...presets.values()].map((p) => ({ ...p, creeps: p.creeps.map((c) => creepKey.get(c)) })),
    }];
  });
  return { battleType: 21, bosses: keyed(list), creeps };
}

// Campaign (AdventuretdLevelLO, id = stage*10, battleGroundCode must exist — same check as the
// stage range above). Each stage's _round list references AdventuretdRoundLO rows: _roundType 3 is
// the stage boss (one elite creep spawning at the back row, pos 7 — stages 1-2 have none), 1/2/4
// are the trash waves, 8 the stage 1-2 tutorial rounds, and 9 the enemy fountain (Suối Dị Thú, a
// spawner building with a placeholder desc — left out entirely). The stage hover popover only
// needs boss + the distinct minion types, so stages keep boss + deduped minion codes (not the
// full round/wave dump), and creeps-dict.json's `campaign` section carries name + desc per creep
// code (same simpleDesc weakness/resistance/trait format as the capital bosses).
function campaignCatalogs(M, V) {
  const creep = (code) => {
    const row = M("CreepLO").get(code);
    if (!row) throw new Error(`campaign creep ${code} missing from CreepLO`);
    const vi = V("CreepLO").get(code);
    // star = CreepLO._type: same-name star variants differ (20s/30s waves), so the stage popover
    // can label the repeat instead of leaving it to read as a dup.
    return { code, name: row.name, name_vn: vi?.name, star: row._type, desc: strip(row.simpleDesc), desc_vn: strip(vi?.simpleDesc) };
  };
  const creeps = {};
  const stages = {};
  for (const row of rows(M("AdventuretdLevelLO")).sort((a, b) => a.id - b.id)) {
    const stage = row.id / 10;
    if (!Number.isInteger(stage) || !M("BattleGroundLO").get(row.battleGroundCode)) continue;
    const minions = new Set();
    let boss = null;
    for (const code of JSON.parse(row._round)) {
      const round = M("AdventuretdRoundLO").get(code);
      if (!round) continue;
      const codes = JSON.parse(round._creep);
      if (round._roundType === 3) boss = codes[0];
      else if (round._roundType !== 9) codes.forEach((c) => minions.add(c));
    }
    minions.delete(boss);
    if (boss) creeps[boss] = creep(boss);
    [...minions].sort((a, b) => a - b).forEach((code) => { creeps[code] = creep(code); });
    stages[stage] = { boss, minions: [...minions].sort((a, b) => a - b) };
  }
  return { stages, creeps };
}

// Blood Night (组队副本血夜, TeamExpedition16, battleType 47; solo 48 uses the same tables). Battle
// level = TeamExpandLO id (1001-1080 = "Ải 1"-"Ải 80"). Each level's _round list references
// TeamExpandRoundLO rows whose id prefix (id / 1e6) gives the role: 1 = trash waves (the 3 creep
// types of _showCreep), 4 = the 3 mini bosses (the xx02 variant of each creep family, 40/90/140s),
// 3 = the final boss (_showBoss, 190s). _roundType does not tell them apart (some mini-boss rows
// are type 1), so the prefix is the rule; showBoss/showCreep are checked against it. The map has
// few monster types, so boss, mini bosses and creeps share one dict: `monsters` (kind + the level
// ids each appears on) and `levels` (per level: boss, timed mini bosses, creeps, by monster key).
// See battle_sim/docs/planning/blood_night.md.
function bloodNightCatalogs(M, V) {
  const ROLE = { 1: "creep", 3: "boss", 4: "mini_boss" };
  const found = new Map(); // code -> { kind, levels: Set }
  const note = (code, kind, level) => {
    const m = found.get(code) ?? { kind, levels: new Set() };
    if (m.kind !== kind) throw new Error(`blood night creep ${code}: both ${m.kind} and ${kind}`);
    m.levels.add(level);
    found.set(code, m);
  };
  const raw = [];
  for (const row of rows(M("TeamExpandLO")).sort((a, b) => a.id - b.id)) {
    const byRole = { creep: new Set(), boss: [], mini_boss: [] };
    for (const id of JSON.parse(row._round)) {
      const round = M("TeamExpandRoundLO").get(id);
      if (!round) throw new Error(`blood night level ${row.id}: round ${id} missing`);
      const role = ROLE[Math.floor(id / 1e6)];
      if (!role) throw new Error(`blood night level ${row.id}: round ${id} has unknown prefix`);
      for (const code of JSON.parse(round._creep)) {
        note(code, role, row.id);
        if (role === "creep") byRole.creep.add(code);
        else byRole[role].push({ code, time: round._roundTime });
      }
    }
    const creeps = [...byRole.creep].sort((a, b) => a - b);
    const shown = JSON.parse(row._showCreep).sort((a, b) => a - b);
    if (byRole.boss.length !== 1 || byRole.boss[0].code !== row._showBoss) throw new Error(`blood night level ${row.id}: boss != showBoss`);
    if (JSON.stringify(creeps) !== JSON.stringify(shown)) throw new Error(`blood night level ${row.id}: creeps != showCreep`);
    raw.push({ id: row.id, level: row._showlevel, battleGroundCode: row._battleGroundCode,
      boss: byRole.boss[0], miniBosses: byRole.mini_boss.sort((a, b) => a.time - b.time), creeps });
  }
  // Mini bosses share the name of their creep family, so they key as "<name> mini".
  const monsters = keyed([...found].sort(([a], [b]) => a - b).map(([code, { kind, levels }]) => {
    const row = M("CreepLO").get(code);
    if (!row) throw new Error(`blood night creep ${code} missing from CreepLO`);
    const vi = V("CreepLO").get(code);
    return [kind === "mini_boss" ? `${row.name} mini` : row.name, { code, name: row.name, name_vn: vi?.name, kind,
      avatar: row.avatar, desc: strip(row.simpleDesc), desc_vn: strip(vi?.simpleDesc) || strip(row.simpleDesc),
      levels: [...levels].sort((a, b) => a - b) }];
  }));
  const key = new Map(Object.entries(monsters).map(([k, m]) => [m.code, k]));
  const levels = Object.fromEntries(raw.map((l) => [l.id, { level: l.level, battleGroundCode: l.battleGroundCode,
    boss: { monster: key.get(l.boss.code), time: l.boss.time },
    miniBosses: l.miniBosses.map((m) => ({ monster: key.get(m.code), time: m.time })),
    creeps: l.creeps.map((c) => key.get(c)) }]));
  return { battleType: 47, levels, monsters };
}

main().catch((e) => { console.error(e); process.exit(1); });

"use strict";
// Generate the playtest catalogs from the game's own config tables:
// - web/dict/map-dict.json: what can be played: campaign stage range, capital (U Đô) bosses + creep presets;
// - web/dict/antique-dict.json: antiques with ranks, suits, colors and upgrade costs (the bulk of the data);
// - web/dict/relic-dict.json: Thánh Khí (relics) by line and purification step, with their skills;
// - web/dict/artifact-dict.json: Thần Khí by hero, quality and stage, with battle skill entries;
// - web/dict/profile-dict.json: the rest of the account side: heroes with their skins, Summoner skins,
//   traps, pets, spells (daoists), building skins and mounts.
// Entries are keyed by a slug of the English name. `name` / `name_vn` come from the game's language packs (lang_en /
// lang_vi.<ver>.bin, public CDN next to config.bin; downloaded once into
// .tmp/battle_sim/config/<configVersion>/).
//
//   node battle_sim/scripts/gen_profile_dict.js [configVersion]   (default sea_65380)
const fs = require("fs");
const path = require("path");
const { Sim } = require("../lib/sim");
const versions = require("../lib/versions");

const CONFIG_VERSION = process.argv[2] || "sea_65380";
const ASSETS = { battleVersion: "2.3.1-2_E63294_P63528_C63583", configVersion: CONFIG_VERSION, mapVersion: "trunk_61543" };
const OUT = path.join(__dirname, "..", "web", "dict", "profile-dict.json");
const MAP_OUT = path.join(__dirname, "..", "web", "dict", "map-dict.json");
const ANTIQUE_OUT = path.join(__dirname, "..", "web", "dict", "antique-dict.json");
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
function fields(row, jsonFields = []) {
  return Object.fromEntries(Object.entries(row).map(([key, value]) => {
    const field = key.slice(1);
    return [field, jsonFields.includes(field) ? jsonField(value) : value];
  }));
}
function maxBy(lo, field) { // mecType -> max of field
  const max = new Map();
  for (const r of rows(lo)) max.set(r.mecType, Math.max(max.get(r.mecType) || 0, r[field]));
  return max;
}

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

  // Hero and Summoner skins share DermaLO and DermaStarLO.
  const dermaMaxStar = new Map();
  for (const r of rows(M("DermaStarLO"))) dermaMaxStar.set(r.dermaCode, Math.max(dermaMaxStar.get(r.dermaCode) || 0, r.star));
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
    ...(!d.skills?.length && isEventReward(d) && d.hideStar ? {
      ...eventUnlock(d, d.costs),
      passiveAttr: jsonField(M("DermaStarLO").get(d.code * 100 + 1)?.attr),
    } : {}),
    ...(d.exclusion ? { excludes: d.exclusion } : {}),
  }]));

  // Dị Năng (异能) skill nodes per hero subType: AvatarUpGradeLO rows with a skillcode, one per
  // chapter 1-5, in chapter order (level N = the first N). Each swaps `replaces` for `skill` in
  // hero.skills (adds it when replaces is null); the server builds hero.skills exactly by this rule.
  // Attribute nodes are left out (server-side attr, not modelled). See docs/planning/hero_gear.md.
  const avatarRows = new Map();
  for (const row of rows(M("AvatarUpGradeLO"))) {
    if (!row.skillcode) continue;
    const point = M("AvatarLO").get(row.pointCode);
    const list = avatarRows.get(point.subType) || [];
    list.push({ chapter: point.chapter, node: { replaces: row.oldSkillCode || null, skill: row.skillcode } });
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
        ...(requires.length ? { requires } : {}),
      };
    }
    return [h.name, { code: h.code, name: h.name, name_vn: vn("HeroLO", h.code), color: RARITY[h.color] || h.color, baseSkills,
      ...(own.length ? { skins } : {}), ...(avatarNodes.has(h.subType) ? { avatarNodes: avatarNodes.get(h.subType) } : {}) }];
  }));

  const organLevel = maxBy(M("OrganUpGradeLO"), "level"), organStar = maxBy(M("OrganStarLO"), "star");
  const traps = keyed(rows(M("OrganLO")).sort((a, b) => a.code - b.code).map((o) => [o.name,
    { code: o.code, name: o.name, name_vn: vn("OrganLO", o.code), color: RARITY[o.color] || o.color, maxLevel: organLevel.get(o.mecType) || 1, maxStar: organStar.get(o.mecType) || 1 }]));

  const petLevel = maxBy(M("SummonCreatureUpGradeLO"), "level"), petStar = maxBy(M("SummonCreatureStarLO"), "star");
  const pets = keyed(rows(M("SummonCreatureLO")).sort((a, b) => a.code - b.code).map((p) => [p.name,
    { code: p.code, name: p.name, name_vn: vn("SummonCreatureLO", p.code), color: RARITY[p.color] || p.color, maxLevel: petLevel.get(p.mecType) || 1, maxStar: petStar.get(p.mecType) || 1 }]));

  const spellStar = maxBy(M("DaoistStarLO"), "star");
  const spells = keyed(rows(M("DaoistLO")).sort((a, b) => a.code - b.code).map((d) => [d.name,
    { code: d.code, name: d.name, name_vn: vn("DaoistLO", d.code), maxStar: spellStar.get(d.mecType) || 1 }]));

  // Building skins: BuildSkinLO rows are per star (code = skinId * 100 + star).
  const buildSkins = new Map();
  for (const r of rows(M("BuildSkinLO"))) {
    const prev = buildSkins.get(r.skinId);
    if (!prev || r.star > prev.maxStar) buildSkins.set(r.skinId, { row: prev?.row?.star === 1 ? prev.row : r, maxStar: r.star });
    if (r.star === 1) buildSkins.get(r.skinId).row = r;
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
  const maps = { campaign: { minStage: stages[0], maxStage: stages[stages.length - 1], stages: stages.length }, capital: capitalMaps(M, V) };

  const mountRanks = rows(M("MountStarLO"));
  const mounts = keyed(rows(M("MountLO")).map((mount) => [mount.name, {
    code: mount.id, name: mount.name, name_vn: vn("MountLO", mount.id),
    color: RARITY[mount.color] ?? mount.color,
    ...(mount.displayA ? { frontModel: mount.displayA } : {}),
    backModel: mount.displayB, hiddenUntilOwned: !!mount.bHideCond,
    ranks: mountRanks.filter((rank) => rank.mecType === mount.id).sort((a, b) => a.star - b.star).map((rank) => ({
      code: rank.code, star: rank.star, attr: Object.fromEntries(jsonField(rank.attr)),
      privileges: jsonField(rank.privilege),
      ...(rank.showSkill ? { showSkill: { code: rank.showSkill, name: SkillBase.get(rank.showSkill)?.name,
        name_vn: vn("SkillBaseLO", rank.showSkill) } } : {}),
    })),
  }]));
  const mountPrivilegeTypes = { 1: "MoveSpeed", 2: "PassWall", 3: "GVGEnergy", 4: "GVGShow" };

  const starRows = rows(M("AntiqueStarLO"));
  const haloRows = rows(M("AntiqueHaloLO"));
  const antiqueColors = Object.fromEntries(rows(M("AntiqueColorLO")).map((row) => [row.color, {
    ...fields(row), name_vn: vn("AntiqueColorLO", row.color), color: RARITY[row.color] ?? row.color,
  }]));
  const antiques = keyed(rows(M("AntiqueLO")).map((row) => {
    const stars = starRows.filter((rank) => rank.type === row.type).sort((a, b) => a.star - b.star);
    const ranks = haloRows.filter((halo) => halo.antiqueCode === row.code).sort((a, b) => a.star - b.star).map((halo) => {
      const show = M("AntiqueHaloShowLO").get(halo.code);
      const showVn = V("AntiqueHaloShowLO").get(halo.code);
      const upgrade = stars.find((rank) => rank.star === halo.star);
      return {
        ...fields(halo, ["showAttr", "attr", "haloParameter", "upAttr", "privilege", "skillFactor", "limitSkillFactor",
          "skillEffTypeParams", "skillTemplateParams", "perPower"]),
        ...(upgrade ? { upgrade: fields(upgrade, ["costs"]) } : {}),
        ...(show ? { display: { ...fields(show), text_vn: showVn?.text,
          showAttrText1_vn: showVn?.showAttrText1, showAttrText2_vn: showVn?.showAttrText2 } } : {}),
      };
    });
    const task = M("AntiqueHaloTaskLO").get(row.type);
    return [row.name, {
      ...fields(row, ["costs", "dupeCosts", "upAttr"]), colorId: row.color, color: RARITY[row.color] ?? row.color,
      name_vn: vn("AntiqueLO", row.code), desc_vn: V("AntiqueLO").get(row.code)?.desc,
      maxStar: stars.at(-1)?.star, ...(task ? { task: fields(task) } : {}), ranks,
    }];
  }));
  const suitRanks = rows(M("AntiqueSuitAttrLO"));
  const antiqueSuits = keyed(rows(M("AntiqueSuitLO")).map((row) => [row.name, {
    ...fields(row, ["types"]), name_vn: vn("AntiqueSuitLO", row.type),
    ranks: suitRanks.filter((rank) => rank.type === row.type).map((rank) => fields(rank, ["showAttr", "attr"])),
  }]));
  const antiqueUpgradeCosts = Array.from(M("AntiqueUpGradeLO").store, (row) => fields(row, ["costs"]));

  // Thánh Khí (圣器, RelicLO type 2). Quality 6-8 relics come in 7 lines (code 82QQLL01, LL = line):
  // red (Q=06) -> gold (07) -> colorful (08), each step a purification (thanh tẩy, RelicQualityUpLO,
  // star kept). Per line: one star-tier skill (same codes at every purification) and, from gold
  // on, one fixed skill. Quality 1-5 relics (no skill) are left out. Stats are left out: they reach battle
  // already merged into hero.attr by the server, the client computes none; see docs/planning/hero_gear.md.
  const RELIC_COLOR = { ...RARITY, 8: "colorful" };
  const relicStars = rows(M("RelicStarLO"));
  const skillRef = (code) => ({ code, name: SkillBase.get(code)?.name, name_vn: vn("SkillBaseLO", code),
    desc_vn: V("SkillBaseLO").get(code)?.desc?.trim() });
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

  // Thần Khí (神器). Keep the refine entries consumed as skills from battleEntryInfos.
  // The battle receives ordinary equipment and refine stats already in hero.attr.
  const artifactRows = rows(M("ArtifactLO")).sort((a, b) => a.code - b.code);
  const artifactHeroes = {};
  const entryPools = {};
  const artifactSkillCodes = new Set();
  for (const row of artifactRows) {
    const hero = artifactHeroes[row.hero] ??= { variants: [] };
    const skillCodes = jsonField(row.skillList);
    skillCodes.forEach((code) => artifactSkillCodes.add(code));
    hero.variants.push({
      code: row.code, name: row.name, name_vn: vn("ArtifactLO", row.code),
      quality: row.quality, stage: row.stage,
      skillCodes, holeNum: row.holeNum, maxHoleNum: row.maxHoleNum, entryPool: row.entryPool,
    });
    entryPools[row.entryPool] ??= {};
  }
  for (const row of rows(M("ArtifactEntryLO")).sort((a, b) => a.code - b.code)) {
    const pool = entryPools[row.entryPool];
    if (!pool || row.entryType !== 2 || !row.skillCode) continue;
    artifactSkillCodes.add(row.skillCode);
    pool[row.code] = {
      quality: row.quality, skillCode: row.skillCode,
      minValue: row.minValue, maxValue: row.maxValue,
      ...(row.skillTemplateParams ? { skillTemplateParams: jsonField(row.skillTemplateParams) } : {}),
    };
  }
  const artifactSkills = Object.fromEntries([...artifactSkillCodes].sort((a, b) => a - b).map((code) => {
    if (!SkillBase.get(code)) throw new Error(`artifact skill ${code} missing from SkillBaseLO`);
    return [code, skillRef(code)];
  }));

  const dict = {
    _generated: `node battle_sim/scripts/gen_profile_dict.js ${CONFIG_VERSION} (names: lang_en, name_vn: lang_vi)`,
    heroes, summonerSkins, traps, pets, spells, buildings, mounts, mountPrivilegeTypes,
  };
  const write = (file, data) => fs.writeFileSync(file, JSON.stringify({ _generated: dict._generated, ...data }, null, 2) + "\n");
  fs.writeFileSync(OUT, JSON.stringify(dict, null, 2) + "\n");
  write(MAP_OUT, maps);
  write(ANTIQUE_OUT, { antiques, antiqueColors, antiqueSuits, antiqueUpgradeCosts });
  write(RELIC_OUT, relics);
  write(ARTIFACT_OUT, { heroes: artifactHeroes, entryPools, skills: artifactSkills });
  const count = (o) => Object.keys(o).length;
  const artifactEntryCount = Object.values(entryPools).reduce((sum, pool) => sum + count(pool), 0);
  console.log(`wrote ${path.relative(process.cwd(), ARTIFACT_OUT)}: ${artifactRows.length} variants, ${artifactEntryCount} battle entries in ${count(entryPools)} pools`);
  console.log(`wrote ${path.relative(process.cwd(), RELIC_OUT)}: ${count(relics.lines)} relic lines`);
  console.log(`wrote ${path.relative(process.cwd(), MAP_OUT)}: campaign stages ${maps.campaign.minStage}-${maps.campaign.maxStage}, ` +
    `${count(maps.capital.bosses)} capital bosses`);
  console.log(`wrote ${path.relative(process.cwd(), ANTIQUE_OUT)}: ${count(antiques)} antiques, ${count(antiqueSuits)} suits`);
  console.log(`wrote ${path.relative(process.cwd(), OUT)}: ${count(heroes)} heroes, ${count(traps)} traps, ` +
    `${count(pets)} pets, ${count(spells)} spells, ${count(summonerSkins)} Summoner skins, ` +
    Object.entries(buildings).map(([k, b]) => `${k} ${count(b.skins)} skins`).join(", "));
}

// Capital (U Đô, GuildNavalWar, battleType 21). Battle level = day*10000 + pos*100 + index and the
// game reads GuildNavalWarLO.get(day*10000 + pos*100): index is ignored, and every row has the
// same creep stat levels, so a room's size never changes the battle. A row only picks the boss and
// its 3 creep types (showCreep = [boss, creepA, creepB, creepC]; the round list follows from it).
// Rows with the same showCreep play the same battle, so each is one preset; `rooms` lists where
// it shows up in the week. See battle_sim/docs/planning/capital.md.
function capitalMaps(M, V) {
  const strip = (s) => String(s || "").replace(/<br\s*\/?>/gi, " · ").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").replace(/\s*·\s*/g, " · ").trim();
  const creep = (code) => {
    const row = M("CreepLO").get(code);
    return { code, name: row.name, name_vn: V("CreepLO").get(code)?.name };
  };
  const roomByPos = new Map(rows(M("GuildNavalWarMapLO")).map((r) => [r.position, r]));
  const bosses = new Map();
  for (const row of rows(M("GuildNavalWarLO")).sort((a, b) => a.id - b.id)) {
    const [bossCode, ...creeps] = JSON.parse(row.showCreep);
    const pos = Math.floor((row.id % 10000) / 100);
    if (!bosses.has(bossCode)) bosses.set(bossCode, new Map());
    const presets = bosses.get(bossCode);
    if (!presets.has(row.showCreep)) presets.set(row.showCreep, { level: row.id + 1, creeps: creeps.map(creep), rooms: [] });
    presets.get(row.showCreep).rooms.push({ day: row.day, pos, roomLevel: roomByPos.get(pos)?.level });
  }
  const roomTypes = {};
  for (const r of roomByPos.values()) {
    if (r.type === 1) roomTypes[r.level] = { name: r.name, name_vn: V("GuildNavalWarMapLO").get(r.id)?.name, seats: r.bedSpace };
  }
  const list = [...bosses].sort(([a], [b]) => a - b).map(([code, presets]) => {
    const row = M("CreepLO").get(code);
    const vi = V("CreepLO").get(code);
    return [row.name, {
      ...creep(code), avatar: row.avatar, desc: strip(row.simpleDesc), desc_vn: strip(vi?.simpleDesc),
      presets: [...presets.values()],
    }];
  });
  return { battleType: 21, roomTypes, bosses: keyed(list) };
}

main().catch((e) => { console.error(e); process.exit(1); });

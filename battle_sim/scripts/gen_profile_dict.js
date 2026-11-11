"use strict";
// Generate web/profile-dict.json (playtest profile catalog) from the game's own config tables:
// campaign stage range, heroes with their skins, traps, pets, spells (daoists) and building skins, keyed by a slug
// of the English name. `name` / `name_vn` come from the game's language packs (lang_en /
// lang_vi.<ver>.bin, public CDN next to config.bin; downloaded once into
// .tmp/battle_sim/config/<configVersion>/).
//
//   node battle_sim/scripts/gen_profile_dict.js [configVersion]   (default sea_65380)
const fs = require("fs");
const path = require("path");
const https = require("https");
const { Sim } = require("../lib/sim");
const versions = require("../lib/versions");

const CONFIG_VERSION = process.argv[2] || "sea_65380";
const ASSETS = { battleVersion: "2.3.1-2_E63294_P63528_C63583", configVersion: CONFIG_VERSION, mapVersion: "trunk_61543" };
const LANG_BASE = "https://mg-sea-cdnres.bighost.games/sea/remoteConfig/sea/";
const OUT = path.join(__dirname, "..", "web", "profile-dict.json");
const BUILDINGS = { door: 1, bed: 2, generator: 3, cat: 4 }; // EBuildType: Door, Bed, WoodenFish, GoldenToad
const SKIN_COLOR = { 4: "default", 6: "red", 7: "gold", 8: "colorful" };
const BUILD_SLOT = { 0: "none", 1: "red", 2: "gold", 3: "special" };

function download(url, file) {
  if (fs.existsSync(file)) return Promise.resolve();
  return new Promise((ok, ko) => {
    https.get(url, (res) => {
      if (res.statusCode !== 200) { res.resume(); return ko(new Error(`${url}: HTTP ${res.statusCode}`)); }
      const tmp = file + ".part";
      res.pipe(fs.createWriteStream(tmp)).on("finish", () => { fs.renameSync(tmp, file); ok(); });
    }).on("error", ko);
  });
}

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
function maxBy(lo, field) { // mecType -> max of field
  const max = new Map();
  for (const r of rows(lo)) max.set(r.mecType, Math.max(max.get(r.mecType) || 0, r[field]));
  return max;
}

async function main() {
  const files = await versions.ensureConfig(CONFIG_VERSION);
  const assets = await versions.resolveAssets(ASSETS);
  // One loader per language: *LO names are translated while rows parse, so the language
  // pack is loaded before any table is read, and each loader keeps its own tables.
  async function tablesIn(lang) {
    const langFile = path.join(path.dirname(files.config), `${lang}.bin`);
    await download(`${LANG_BASE}${lang}.${CONFIG_VERSION.split("_").pop()}.bin`, langFile);
    const req = new Sim(assets).req;
    const reader = new (req("BinaryReader").BinaryReader)();
    reader.init(req("QuickLZ").QuickLZ.decompress(new Uint8Array(fs.readFileSync(langFile))));
    if (!new (req("LangParser").LangParser)().writeBinaryDataImmediately(reader)) throw new Error(`${lang} pack failed`);
    return (n) => req(n)[n];
  }
  const M = await tablesIn("lang_en");
  const V = await tablesIn("lang_vi");
  const vn = (table, key) => V(table).get(key)?.name;
  const SkillBase = M("SkillBaseLO");

  // Heroes: base skills 10<NN><slot><lv=01>000 for slots 1-3; skins from DermaLO/DermaStarLO.
  const dermaMaxStar = new Map();
  for (const r of rows(M("DermaStarLO"))) dermaMaxStar.set(r.dermaCode, Math.max(dermaMaxStar.get(r.dermaCode) || 0, r.star));
  const dermas = rows(M("DermaLO")).filter((d) => d.dermatype === 1);
  const heroes = keyed(rows(M("HeroLO")).filter((h) => h.isShow).sort((a, b) => a.code - b.code).map((h) => {
    const nn = String(h.code % 1000).padStart(2, "0");
    const baseSkills = [1, 2, 3].map((slot) => Number(`10${nn}0${slot}01000`)).filter((id) => SkillBase.get(id));
    // DermaLO.heroCode holds HeroLO.subType (DermaStarLO.heroCode holds the hero code).
    const own = dermas.filter((d) => d.heroCode === h.subType).sort((a, b) => a.index - b.index || a.code - b.code);
    const skinKey = new Map(Object.entries(keyed(own.map((d) => [d.name, d]))).map(([k, d]) => [d.code, k]));
    const skins = {};
    for (const d of own) {
      const requires = JSON.parse(d.requirement || "[]").map(([code]) => skinKey.get(code));
      skins[skinKey.get(d.code)] = {
        code: d.code, name: d.name, name_vn: vn("DermaLO", d.code), color: SKIN_COLOR[d.color] || d.color, maxStar: dermaMaxStar.get(d.code) || 1,
        ...(requires.length ? { requires } : {}),
      };
    }
    return [h.name, { code: h.code, name: h.name, name_vn: vn("HeroLO", h.code), baseSkills, ...(own.length ? { skins } : {}) }];
  }));

  const organLevel = maxBy(M("OrganUpGradeLO"), "level"), organStar = maxBy(M("OrganStarLO"), "star");
  const traps = keyed(rows(M("OrganLO")).sort((a, b) => a.code - b.code).map((o) => [o.name,
    { code: o.code, name: o.name, name_vn: vn("OrganLO", o.code), maxLevel: organLevel.get(o.mecType) || 1, maxStar: organStar.get(o.mecType) || 1 }]));

  const petLevel = maxBy(M("SummonCreatureUpGradeLO"), "level"), petStar = maxBy(M("SummonCreatureStarLO"), "star");
  const pets = keyed(rows(M("SummonCreatureLO")).sort((a, b) => a.code - b.code).map((p) => [p.name,
    { code: p.code, name: p.name, name_vn: vn("SummonCreatureLO", p.code), maxLevel: petLevel.get(p.mecType) || 1, maxStar: petStar.get(p.mecType) || 1 }]));

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
      };
    }
    buildings[id] = { buildType, skins };
  }

  // Campaign stages: AdventuretdLevelLO id = stage * 10, with a BattleGround (same check as profile.js).
  const stages = rows(M("AdventuretdLevelLO")).map((r) => r.id / 10)
    .filter((stage) => Number.isInteger(stage) && M("BattleGroundLO").get(M("AdventuretdLevelLO").get(stage * 10).battleGroundCode))
    .sort((a, b) => a - b);
  const maps = { campaign: { minStage: stages[0], maxStage: stages[stages.length - 1], stages: stages.length } };

  const dict = {
    _generated: `node battle_sim/scripts/gen_profile_dict.js ${CONFIG_VERSION} (names: lang_en, name_vn: lang_vi)`,
    maps, heroes, traps, pets, spells, buildings,
  };
  fs.writeFileSync(OUT, JSON.stringify(dict, null, 2) + "\n");
  const count = (o) => Object.keys(o).length;
  console.log(`wrote ${path.relative(process.cwd(), OUT)}: campaign stages ${maps.campaign.minStage}-${maps.campaign.maxStage}, ${count(heroes)} heroes, ${count(traps)} traps, ` +
    `${count(pets)} pets, ${count(spells)} spells, ` +
    Object.entries(buildings).map(([k, b]) => `${k} ${count(b.skins)} skins`).join(", "));
}

main().catch((e) => { console.error(e); process.exit(1); });

"use strict";
// Tranh Bá event catalog; names and schedules come from the game's config, never the weekly pool.
// node battle_sim/scripts/gen_naval_dict.js [configVersion] [battleVersion]
const fs = require("fs");
const path = require("path");
const { Sim } = require("../lib/sim");
const versions = require("../lib/versions");
const rows = (table) => { const out = []; table.store.foreach((_k, row) => out.push(row)); return out; };
const slug = (name) => name.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
const strip = (s) => String(s || "").replace(/<br\s*\/?>/gi, " · ").replace(/<[^>]+>/g, "").trim();

function navalCatalogs(M, V) {
  const bosses = {}, creeps = {};
  const monster = (code) => {
    const en = M("CreepLO").get(code), vi = V("CreepLO").get(code);
    if (!en) throw new Error(`Naval creep ${code} missing`);
    return { code, name: en.name, name_vn: vi?.name, avatar: en.avatar,
      desc: strip(en.simpleDesc), desc_vn: strip(vi?.simpleDesc) };
  };
  for (const row of rows(M("GuildNavalMonthwarLO")).sort((a, b) => a.id - b.id)) {
    // Setup supports room occupation only; never export audition bosses, presets or companions.
    if (row.subType === 0) continue;
    const [bossCode, ...companions] = JSON.parse(row.showCreep);
    const rounds = JSON.parse(row.round).map((id) => {
      const round = M("GuildNavalMonthwarRoundLO").get(id);
      if (!round) throw new Error(`Naval level ${row.id}: missing round ${id}`);
      return round;
    });
    const bossCodes = rounds.filter((r) => r.roundType === 3).flatMap((r) => JSON.parse(r.creep));
    if (bossCodes.length !== 1 || bossCodes[0] !== bossCode) throw new Error(`Naval level ${row.id}: boss != showCreep`);
    if (!M("BattleGroundLO").get(row.battleGroundCode)) throw new Error(`Naval level ${row.id}: missing battleground`);
    const boss = monster(bossCode), key = `${slug(boss.name) || 'boss'}_${bossCode}`;
    bosses[key] ||= { ...boss, presets: [] };
    for (const code of companions) creeps[code] ||= monster(code);
    bosses[key].presets.push({ level: row.id + 1, phase: "rooms",
      subType: row.subType, day: row.day, position: Math.floor(row.id / 100) % 100,
      creeps: companions });
  }
  return { battleType: 42, bosses, creeps };
}

async function main() {
  const configVersion = process.argv[2] || "sea_66328";
  const battleVersion = process.argv[3] || "2.3.1-2_E64067_P63528_C64067";
  const assets = await versions.resolveAssets({ configVersion, battleVersion, mapVersion: "trunk_61543" });
  async function tables(lang) {
    const req = new Sim(assets).req;
    const reader = new (req("BinaryReader").BinaryReader)();
    reader.init(req("QuickLZ").QuickLZ.decompress(new Uint8Array(fs.readFileSync(await versions.ensureLanguage(configVersion, lang)))));
    if (!new (req("LangParser").LangParser)().writeBinaryDataImmediately(reader)) throw new Error(`Invalid ${lang} pack`);
    return (name) => req(name)[name];
  }
  const catalog = navalCatalogs(await tables("en"), await tables("vi"));
  const out = path.join(__dirname, "../web/dict/naval-boss-dict.json");
  fs.writeFileSync(out, JSON.stringify({ _generated: `node battle_sim/scripts/gen_naval_dict.js ${configVersion} ${battleVersion}`, ...catalog }, null, 2) + "\n");
  console.log(`wrote ${out}: ${Object.keys(catalog.bosses).length} bosses, ${Object.values(catalog.bosses).reduce((n, b) => n + b.presets.length, 0)} presets`);
}
if (require.main === module) main().catch((err) => { console.error(err); process.exitCode = 1; });
module.exports = { navalCatalogs };

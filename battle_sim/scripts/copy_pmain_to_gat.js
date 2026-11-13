"use strict";

// Create an offline GAT playtest capture using a VN capture's hero lineup.
const fs = require("node:fs");
const path = require("node:path");
const { randomBytes } = require("node:crypto");
const { parseArgs } = require("node:util");
const { CAPTURE_DIR, listItems, loadCapture } = require("../lib/capture");
const { Sim } = require("../lib/sim");
const { bundleVersion } = require("../lib/versions");

const gatDir = path.join(CAPTURE_DIR, "..", "skin-research-cn");
const bundle = path.join(gatDir, "index.cda14.js");
const configVersion = "trunk_66196";
const mapVersion = "trunk_61645";

function findBattle(dir, pattern, file, uuid, label) {
  const files = file ? [file] : fs.readdirSync(dir)
    .filter((name) => pattern.test(name))
    .sort().reverse().map((name) => path.join(dir, name));
  for (const captureFile of files) {
    const battle = loadCapture(captureFile).find(({ start }) => !uuid || start.uuid === uuid);
    if (battle) return battle;
  }
  throw new Error(`No complete ${label} battle found`);
}

function main() {
  const { values } = parseArgs({
    options: {
      vn: { type: "string" },
      "vn-uuid": { type: "string" },
      gat: { type: "string" },
      "gat-uuid": { type: "string" },
      help: { type: "boolean", short: "h" },
    },
  });
  if (values.help) {
    console.log("Usage: node battle_sim/scripts/copy_pmain_to_gat.js [--vn capture.jsonl] [--vn-uuid uuid] [--gat capture.jsonl] [--gat-uuid uuid]");
    return;
  }

  const vn = findBattle(CAPTURE_DIR, /^events-pmain-.*\.jsonl$/, values.vn, values["vn-uuid"], "VN pmain");
  const gat = findBattle(gatDir, /^events-pcn-(?!pmain-).*\.jsonl$/, values.gat, values["gat-uuid"], "GAT");
  const start = structuredClone(gat.start);
  if (!/^sea_/.test(vn.start.configVersion) || start.configVersion !== configVersion ||
      start.mapVersion !== mapVersion || start.battleVersion !== bundleVersion(bundle)) {
    throw new Error("Expected a SEA donor and a GAT template matching the cached GAT assets");
  }

  const player = start.playerInfos[0];
  const donor = vn.start.playerInfos[0];
  if (!player || !donor || listItems(donor.heros).length !== 5) {
    throw new Error("Expected a GAT player and a five-hero VN lineup");
  }
  if (listItems(player.builds).some((build) => build.hero)) {
    throw new Error("Use a GAT template without preplaced heroes");
  }

  const sim = new Sim({
    bundle,
    config: path.join(gatDir, "config.66196.bin"),
    preloadConfig: path.join(gatDir, "preload_config.66196.bin"),
    mapsDir: path.join(gatDir, "maps", mapVersion),
  });
  const { HeroLO } = sim.req("HeroLO");
  const { SkillBaseLO } = sim.req("SkillBaseLO");
  for (const hero of [...listItems(donor.heros), donor.support].filter((hero) => hero?.code)) {
    if (!HeroLO.get(hero.code)) throw new Error(`Hero ${hero.code} is missing from GAT config`);
    for (const { code } of listItems(hero.skills)) {
      if (!SkillBaseLO.get(code)) throw new Error(`Hero ${hero.code} skill ${code} is missing from GAT config`);
    }
  }

  player.heros = structuredClone(donor.heros);
  if (donor.support) player.support = structuredClone(donor.support);
  else delete player.support;
  start.uuid = randomBytes(12).toString("hex");
  sim.setup(start);

  // The setup picker requires a QuitRoom event. The template's ops and result
  // belong to a different lineup, so the generated capture is for play mode.
  const quit = { battleType: start.battleType, operations: { _length: 0 } };
  const events = [
    { kind: "room", data: { msg: "StartGameP", obj: start } },
    { kind: "sock", data: { msg: "QuitRoom(", obj: quit } },
  ];
  const output = path.join(gatDir, `events-pcn-pmain-${start.uuid}.jsonl`);
  fs.writeFileSync(output, events.map((event) => JSON.stringify(event)).join("\n") + "\n", { flag: "wx", mode: 0o600 });

  console.log(`GAT playtest capture: ${output}`);
  console.log(`Capture ID: ${start.uuid}`);
  console.log(`GAT template seed: ${gat.start.uuid}`);
  console.log(`VN donor: ${path.basename(vn.file)} (${vn.start.uuid})`);
}

try {
  main();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}

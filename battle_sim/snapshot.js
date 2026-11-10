"use strict";
// Cache the currently live deploy (code bundle + battle maps) for battle_sim.
//   node battle_sim/snapshot.js
// Plain HTTP, no browser: index.html (ClientVer) -> manifest.<ver>.js -> src/settings.<h>.js
// (bundleVers: main, battle, resources). Old deploys disappear from the host, so run this
// whenever the game updates, before capturing battles you want to replay.
const fs = require("fs");
const path = require("path");
const { getText, getJson, download } = require("./lib/http");
const cocos = require("./lib/cocos_bundle");
const versions = require("./lib/versions");

const GAME = "https://hauntedroomvnh5.joynetgame.com/";

async function liveDeploy() {
  const html = await getText(GAME);
  const clientVer = (/"ClientVer":\s*"(\d+)"/.exec(html) || [])[1];
  if (!clientVer) throw new Error("ClientVer not found in index.html");
  const manifest = await getText(`${GAME}manifest.${clientVer}.js`);
  const settingsFile = (/"(src\/settings\.[0-9a-f]+\.js)"/.exec(manifest) || [])[1];
  if (!settingsFile) throw new Error("settings script not found in manifest");
  const settings = await getText(GAME + settingsFile);
  const vers = (/bundleVers:\{([^}]*)\}/.exec(settings) || [])[1];
  if (!vers) throw new Error("bundleVers not found in settings");
  const bundleVers = Object.fromEntries([...vers.matchAll(/(\w+):"([0-9a-f]+)"/g)].map((m) => [m[1], m[2]]));
  return { clientVer, settingsFile, bundleVers };
}

async function fetchMainBundle(hash) {
  const dest = path.join(versions.CACHE, "bundles", `index.${hash}.js`);
  const fresh = await download(`${cocos.ASSET_HOST}main/index.${hash}.js`, dest);
  return { file: dest, fresh, battleVersion: versions.bundleVersion(dest) };
}

async function fetchMapVersion(resourcesHash) {
  const cfg = await cocos.loadBundleConfig("resources", resourcesHash);
  const hit = Object.entries(cfg.paths).find(([, v]) => v[0] === "tiledBgVersion");
  if (!hit) throw new Error("resources/tiledBgVersion not in resources bundle");
  for (const f of cocos.importUrlsFor("resources", cfg, Number(hit[0]))) {
    for (const a of cocos.jsonAssets(await getJson(f.url))) {
      if (a.name === "tiledBgVersion") return `${a.payload.branch}_${a.payload.version}`;
    }
  }
  throw new Error("tiledBgVersion payload not found");
}

// Every Tiled map (layers+tilesets) and tileset (tiles) in the battle bundle.
// Duplicate names (brush/_empty/brush_xx vs brush/xx/brush_xx): most tiles wins.
async function fetchMaps(battleHash, outDir) {
  const cfg = await cocos.loadBundleConfig("battle", battleHash);
  const found = {};
  for (const f of cocos.importUrls("battle", cfg)) {
    for (const { name, payload } of cocos.jsonAssets(await getJson(f.url))) {
      let size;
      if (payload.layers && payload.tilesets) size = 0;
      else if (payload.tiles) size = Object.keys(payload.tiles).length;
      else continue;
      (found[name] = found[name] || []).push({ size, payload });
    }
  }
  if (!found.common) throw new Error("common.json not found in battle bundle");
  const tmp = outDir + ".part";
  fs.rmSync(tmp, { recursive: true, force: true });
  fs.mkdirSync(tmp, { recursive: true });
  let n = 0;
  for (const [name, items] of Object.entries(found)) {
    items.sort((a, b) => b.size - a.size);
    items.forEach((it, i) => {
      fs.writeFileSync(path.join(tmp, i === 0 ? `${name}.json` : `${name}.${i}.json`), JSON.stringify(it.payload));
      n++;
    });
  }
  fs.writeFileSync(path.join(tmp, "_source.json"), JSON.stringify({ battle: battleHash, at: new Date().toISOString() }));
  fs.rmSync(outDir, { recursive: true, force: true });
  fs.renameSync(tmp, outDir);
  return n;
}

async function main() {
  const d = await liveDeploy();
  const { main: mainHash, battle, resources } = d.bundleVers;
  console.log(`live: ClientVer ${d.clientVer}, ${d.settingsFile}, main ${mainHash}, battle ${battle}, resources ${resources}`);

  const b = await fetchMainBundle(mainHash);
  console.log(`bundle ${b.fresh ? "downloaded" : "cached"}: ${path.relative(process.cwd(), b.file)} -> battleVersion ${b.battleVersion}`);
  if (!b.battleVersion) console.warn("WARNING: BATTLE_ENGINE_VERSION not found in bundle");

  const mapVersion = await fetchMapVersion(resources);
  const dir = versions.mapsDir(mapVersion);
  if (fs.existsSync(path.join(dir, "common.json"))) {
    console.log(`maps cached: ${mapVersion}`);
  } else {
    const n = await fetchMaps(battle, dir);
    console.log(`maps ${mapVersion}: ${n} files -> ${path.relative(process.cwd(), dir)}`);
  }
}

main().catch((e) => { console.error(e && e.stack || e); process.exit(1); });

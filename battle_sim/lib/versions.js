"use strict";
// Pick the bundle / config / maps that match a battle's StartGameP versions.
//
//   battleVersion "2.3.1-2_E63294_P63528_C63583" = BATTLE_ENGINE_VERSION + "_" + ENGINE_BRIDGE_VERSION,
//                 both string constants inside the main code bundle.
//   configVersion "sea_65380"   = ConfigParser.branch + "_" + version -> config.65380.bin on the CDN.
//   mapVersion    "trunk_61543" = resources/tiledBgVersion.json of the deploy the maps came from.
//
// Cache (.tmp/battle_sim/):
//   bundles/index.<hash>.js                    main code bundle (also scans .tmp/bundle/main.*/)
//   config/<configVersion>/{config,preload_config}.bin   fetched on demand
//   maps/<mapVersion>/*.json                   Tiled maps + tilesets (written by scripts/snapshot.js)
// The CDN keeps old config versions, so configs are always fetchable. Old code bundles and
// maps are only reachable while live, hence `scripts/snapshot.js` to cache each deploy.
const fs = require("fs");
const path = require("path");
const { download } = require("./http");

const ROOT = path.join(__dirname, "..", "..");
const CACHE = path.join(ROOT, ".tmp", "battle_sim");
const CONFIG_BASE = "https://mg-sea-cdnres.bighost.games/sea/remoteConfig/sea/";
const ENGINE_RE = /BATTLE_ENGINE_VERSION="([^"]+)",\w+\.ENGINE_BRIDGE_VERSION="([^"]+)"/;

function bundleVersionOfSource(src) {
  const m = ENGINE_RE.exec(src);
  return m ? `${m[1]}_${m[2]}` : null;
}

function bundleVersion(file) {
  return bundleVersionOfSource(fs.readFileSync(file, "utf8"));
}

function listDir(dir) {
  try { return fs.readdirSync(dir); } catch { return []; }
}

function candidateBundles() {
  const out = listDir(path.join(CACHE, "bundles"))
    .filter((f) => /^index\.[0-9a-f]+\.js$/.test(f))
    .map((f) => path.join(CACHE, "bundles", f));
  const research = path.join(ROOT, ".tmp", "bundle");
  for (const d of listDir(research).filter((d) => /^main\.[0-9a-f]+$/.test(d))) {
    const f = path.join(research, d, `index.${d.slice(5)}.js`);
    if (fs.existsSync(f)) out.push(f);
  }
  return out;
}

// Every cached bundle grouped by the battleVersion it embeds.
function bundleIndex() {
  const idx = {};
  for (const f of candidateBundles()) {
    const v = bundleVersion(f);
    if (v) (idx[v] = idx[v] || []).push(f);
  }
  return idx;
}

function findBundle(battleVersion) {
  const idx = bundleIndex();
  if (idx[battleVersion]) return idx[battleVersion][0];
  const have = Object.keys(idx).join(", ") || "none";
  throw new Error(`no cached code bundle for battleVersion ${battleVersion} (cached: ${have}). ` +
    "Run `node battle_sim/scripts/snapshot.js` while that version is live.");
}

async function ensureConfig(configVersion) {
  const m = /^(.+)_(\d+)$/.exec(configVersion || "");
  if (!m) throw new Error("bad configVersion: " + configVersion);
  const dir = path.join(CACHE, "config", configVersion);
  const files = { config: path.join(dir, "config.bin"), preloadConfig: path.join(dir, "preload_config.bin") };
  await download(`${CONFIG_BASE}config.${m[2]}.bin`, files.config);
  await download(`${CONFIG_BASE}preload_config.${m[2]}.bin`, files.preloadConfig);
  return files;
}

async function ensureLanguage(configVersion, language) {
  const m = /^(.+)_(\d+)$/.exec(configVersion || "");
  if (!m) throw new Error("bad configVersion: " + configVersion);
  const file = path.join(CACHE, "config", configVersion, `lang_${language}.bin`);
  await download(`${CONFIG_BASE}lang_${language}.${m[2]}.bin`, file);
  return file;
}

function mapsDir(mapVersion) {
  return path.join(CACHE, "maps", mapVersion);
}

function findMaps(mapVersion) {
  const dir = mapsDir(mapVersion);
  if (fs.existsSync(path.join(dir, "common.json"))) return dir;
  const have = listDir(path.join(CACHE, "maps")).join(", ") || "none";
  throw new Error(`no cached maps for mapVersion ${mapVersion} (cached: ${have}). ` +
    "Run `node battle_sim/scripts/snapshot.js` while that version is live.");
}

// Sim constructor paths for a StartGameP; fetches the config if missing.
async function resolveAssets(start) {
  const cfg = await ensureConfig(start.configVersion);
  return {
    bundle: findBundle(start.battleVersion),
    config: cfg.config,
    preloadConfig: cfg.preloadConfig,
    mapsDir: findMaps(start.mapVersion),
  };
}

// Versions the loaded sim actually runs with, in StartGameP format.
function loadedVersions(sim) {
  const CP = sim.req("ConfigParser").ConfigParser;
  return {
    battleVersion: bundleVersion(sim.bundlePath),
    configVersion: `${CP.branch}_${CP.version}`,
    mapVersion: path.basename(sim.mapsDir),
  };
}

module.exports = {
  CACHE, bundleVersion, bundleVersionOfSource, bundleIndex, findBundle,
  ensureConfig, ensureLanguage, mapsDir, findMaps, resolveAssets, loadedVersions,
};

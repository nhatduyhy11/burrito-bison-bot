"use strict";
// Pick the bundle / config / maps that match a battle's StartGameP versions.
//
//   battleVersion "2.3.1-2_E63294_P63528_C63583" = BATTLE_ENGINE_VERSION + "_" + ENGINE_BRIDGE_VERSION,
//                 both string constants inside the main code bundle.
//   configVersion "sea_65380"   = ConfigParser.branch + "_" + version -> config.65380.bin on the CDN.
//   mapVersion    "trunk_61543" = resources/tiledBgVersion.json of the deploy the maps came from.
//
// Cache (.tmp/battle_sim/ for VN, .tmp/battle_sim_gat/ for GAT — see `versions.gat`):
//   bundles/index.<hash>.js                    main code bundle (also scans .tmp/bundle/main.*/, gat.*/ for GAT)
//   config/<configVersion>/{config,preload_config}.bin   fetched on demand
//   maps/<mapVersion>/*.json                   Tiled maps + tilesets (written by scripts/snapshot.js)
// The CDN keeps old config versions, so configs are always fetchable. Old code bundles and
// maps are only reachable while live, hence `scripts/snapshot.js` to cache each deploy.
const fs = require("fs");
const path = require("path");
const { download } = require("./http");

const ROOT = path.join(__dirname, "..", "..");
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

// One region's cache: VN (default export) or GAT (`.gat`).
//   game         public game host (index.html, assets/)
//   cache        cache root
//   configBase   remote config CDN
//   researchPrefix  extra bundle dirs .tmp/bundle/<prefix>.<hash>/index.<hash>.js
function region({ name, game, cache, configBase, researchPrefix }) {
  function candidateBundles() {
    const out = listDir(path.join(cache, "bundles"))
      .filter((f) => /^index\.[0-9a-f]+\.js$/.test(f))
      .map((f) => path.join(cache, "bundles", f));
    const research = path.join(ROOT, ".tmp", "bundle");
    const re = new RegExp(`^${researchPrefix}\\.([0-9a-f]+)$`);
    for (const d of listDir(research)) {
      const m = re.exec(d);
      const f = m && path.join(research, d, `index.${m[1]}.js`);
      if (f && fs.existsSync(f)) out.push(f);
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

  const snapshotHint = `Run \`node battle_sim/scripts/snapshot.js${name === "gat" ? " --gat" : ""}\` while that version is live.`;

  function findBundle(battleVersion) {
    const idx = bundleIndex();
    if (idx[battleVersion]) return idx[battleVersion][0];
    const have = Object.keys(idx).join(", ") || "none";
    throw new Error(`no cached ${name} code bundle for battleVersion ${battleVersion} (cached: ${have}). ${snapshotHint}`);
  }

  function configNumber(configVersion) {
    const m = /^(.+)_(\d+)$/.exec(configVersion || "");
    if (!m) throw new Error("bad configVersion: " + configVersion);
    return m[2];
  }

  async function ensureConfig(configVersion) {
    const n = configNumber(configVersion);
    const dir = path.join(cache, "config", configVersion);
    const files = { config: path.join(dir, "config.bin"), preloadConfig: path.join(dir, "preload_config.bin") };
    await download(`${configBase}config.${n}.bin`, files.config);
    await download(`${configBase}preload_config.${n}.bin`, files.preloadConfig);
    return files;
  }

  async function ensureLanguage(configVersion, language) {
    const n = configNumber(configVersion);
    const file = path.join(cache, "config", configVersion, `lang_${language}.bin`);
    await download(`${configBase}lang_${language}.${n}.bin`, file);
    return file;
  }

  function mapsDir(mapVersion) {
    return path.join(cache, "maps", mapVersion);
  }

  function findMaps(mapVersion) {
    const dir = mapsDir(mapVersion);
    if (fs.existsSync(path.join(dir, "common.json"))) return dir;
    const have = listDir(path.join(cache, "maps")).join(", ") || "none";
    throw new Error(`no cached ${name} maps for mapVersion ${mapVersion} (cached: ${have}). ${snapshotHint}`);
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

  return {
    name, GAME: game, CACHE: cache, ASSET_HOST: game + "assets/",
    bundleIndex, findBundle, ensureConfig, ensureLanguage, mapsDir, findMaps, resolveAssets,
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

const vn = region({
  name: "vn", game: "https://hauntedroomvnh5.joynetgame.com/", cache: path.join(ROOT, ".tmp", "battle_sim"),
  configBase: "https://mg-sea-cdnres.bighost.games/sea/remoteConfig/sea/", researchPrefix: "main",
});
const gat = region({
  name: "gat", game: "https://hauntheroesweb.acenetgame.com/", cache: path.join(ROOT, ".tmp", "battle_sim_gat"),
  configBase: "https://cdnres.bighost.games/gat/remoteConfig/trunk/", researchPrefix: "gat",
});

module.exports = { ...vn, vn, gat, bundleVersion, bundleVersionOfSource, loadedVersions };

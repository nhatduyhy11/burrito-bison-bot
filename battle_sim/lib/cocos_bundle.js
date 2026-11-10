"use strict";
// Read a Cocos Creator 2.4 asset bundle straight from the game host:
// assets/<bundle>/config.<hash>.json + import/<xx>/<uuid|pack>.<ver>.json.
const { getJson } = require("./http");

const ASSET_HOST = "https://hauntedroomvnh5.joynetgame.com/assets/";
const B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

// Compressed 22-char uuid -> 36-char uuid (others returned as-is).
function decodeUuid(u) {
  if (u.length !== 22) return u;
  let hex = u.slice(0, 2);
  let bits = "";
  for (const c of u.slice(2)) bits += B64.indexOf(c).toString(2).padStart(6, "0");
  for (let i = 0; i < 120; i += 4) hex += parseInt(bits.slice(i, i + 4), 2).toString(16);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

async function loadBundleConfig(bundle, hash) {
  return getJson(`${ASSET_HOST}${bundle}/config.${hash}.json`);
}

// URL of every import file (single asset or pack) listed by the config.
function importUrls(bundle, cfg) {
  const uuids = cfg.uuids.map(decodeUuid);
  const imp = (cfg.versions && cfg.versions.import) || [];
  const out = [];
  for (let i = 0; i < imp.length; i += 2) {
    const key = imp[i];
    const name = typeof key === "number" ? uuids[key] : key; // pack ids are strings
    out.push({ name, url: `${ASSET_HOST}${bundle}/import/${name.slice(0, 2)}/${name}.${imp[i + 1]}.json` });
  }
  return out;
}

// Import files that contain the asset at config index `idx` (its own file or packs).
function importUrlsFor(bundle, cfg, idx) {
  const packs = new Set(Object.entries(cfg.packs || {}).filter(([, v]) => v.includes(idx)).map(([k]) => k));
  const own = decodeUuid(cfg.uuids[idx]);
  return importUrls(bundle, cfg).filter((f) => f.name === own || packs.has(f.name));
}

// Named JSON payloads (cc.JsonAsset) inside a compiled import file:
// data[5] = [[ [classIdx, name, payload], ... ], ...].
function* jsonAssets(data) {
  if (!Array.isArray(data) || !Array.isArray(data[5])) return;
  for (const entry of data[5]) {
    const obj = entry && entry[0] && entry[0][0];
    if (Array.isArray(obj) && typeof obj[1] === "string" && obj[2] && typeof obj[2] === "object") {
      yield { name: obj[1], payload: obj[2] };
    }
  }
}

module.exports = { ASSET_HOST, decodeUuid, loadBundleConfig, importUrls, importUrlsFor, jsonAssets };

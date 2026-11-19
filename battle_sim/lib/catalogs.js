"use strict";
const fs = require("fs");
const path = require("path");

const DIR = path.join(__dirname, "..", "web", "dict");
const DICTS = new Set(["hero", "support", "map", "boss", "creeps", "campaign", "antique", "relic", "artifact"]);
const isRecord = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

function merge(base, overrides) {
  if (!isRecord(base) || !isRecord(overrides)) return overrides;
  return {
    ...base,
    ...Object.fromEntries(Object.entries(overrides).map(([key, value]) => [key, merge(base[key], value)])),
  };
}

const readJson = (file) => JSON.parse(fs.readFileSync(path.join(DIR, file), "utf8"));

// region "gat" merges web/dict/gat-overrides.json over the VN dicts. Both are read per request
// (not require()d) so hand edits to the overrides show without restarting serve.js.
function readCatalog(name, region = "vn") {
  if (!DICTS.has(name)) throw new Error(`Unknown catalog: ${name}`);
  const base = readJson(`${name}-dict.json`);
  const overrides = region === "gat" && readJson("gat-overrides.json")[name];
  return overrides ? merge(base, overrides) : base;
}

module.exports = { readCatalog };

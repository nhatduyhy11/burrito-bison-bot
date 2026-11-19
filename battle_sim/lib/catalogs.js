"use strict";
const fs = require("fs");
const path = require("path");

const DIR = path.join(__dirname, "..", "web", "dict");
const GAT_OVERRIDES = require("../web/dict/gat-overrides.json");
const DICTS = new Set(["hero", "support", "map", "boss", "creeps", "campaign", "antique", "relic", "artifact"]);
const isRecord = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

function merge(base, overrides) {
  if (!isRecord(base) || !isRecord(overrides)) return overrides;
  return {
    ...base,
    ...Object.fromEntries(Object.entries(overrides).map(([key, value]) => [key, merge(base[key], value)])),
  };
}

// region "gat" merges web/dict/gat-overrides.json over the VN dicts.
function readCatalog(name, region = "vn") {
  if (!DICTS.has(name)) throw new Error(`Unknown catalog: ${name}`);
  const base = JSON.parse(fs.readFileSync(path.join(DIR, `${name}-dict.json`), "utf8"));
  const overrides = region === "gat" && GAT_OVERRIDES[name];
  return overrides ? merge(base, overrides) : base;
}

module.exports = { readCatalog };

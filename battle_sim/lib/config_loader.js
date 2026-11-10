"use strict";
// Load the game's remote config (config.<ver>.bin) into the bundle's *LO tables,
// using the game's own QuickLZ / BinaryReader / ConfigParser.
const fs = require("fs");

// parser: "ConfigParser" for config.<ver>.bin, "PreloadConfigParser" for
// preload_config.<ver>.bin (holds ConstLO and other early tables).
function loadConfig(req, binPath, parser = "ConfigParser") {
  const raw = new Uint8Array(fs.readFileSync(binPath));
  const QuickLZ = req("QuickLZ").QuickLZ;
  const BinaryReader = req("BinaryReader").BinaryReader;
  const Parser = req(parser)[parser];
  const data = QuickLZ.decompress(raw);
  const reader = new BinaryReader();
  reader.init(data);
  new Parser().writeBinaryDataWhenRead(reader);
  return data.length;
}

module.exports = { loadConfig };

"use strict";
// Region table for serve.js. The region follows the port, like in the sandbox:
// 8090 (and any other port) = VN, 8091 = GAT. A VN server still answers catalog/battle
// requests for GAT when the page asks with ?region=gat (setup page region switch).
const fs = require("fs");
const path = require("path");
const versions = require("./versions");
const capture = require("./capture");

const PORTS = { 8091: "gat" };

// Per-region behaviour that differs from VN.
const REGIONS = {
  vn: {
    name: "vn",
    versions: versions.vn,
    alwaysFill: false, // offline by default; --fill opts in
    liveBoot: false, // needs a mirror.js run first
    locale: null, // deploy.json served as is
    // VN captures: the default capture folders (.tmp/battle_research/).
    loadBattles: () => capture.loadAll(),
  },
  gat: {
    name: "gat",
    versions: versions.gat,
    alwaysFill: true, // always fills missing static assets from the GAT host
    liveBoot: true, // no mirror.js run: first start writes the live deploy's boot files
    locale: "tw",
    // GAT captures: .tmp/battle_sim_gat/events-*.jsonl (recorded with the pcn profile).
    loadBattles() {
      const dir = versions.gat.CACHE;
      const files = fs.existsSync(dir) ? fs.readdirSync(dir).filter((file) => /^events-.*\.jsonl$/.test(file)) : [];
      return capture.loadAll(files.map((file) => path.join(dir, file)));
    },
  },
};

function withPaths(region) {
  const cache = region.versions.CACHE;
  return {
    ...region,
    game: region.versions.GAME,
    cache,
    configDir: path.join(cache, "config"),
    profilesDir: path.join(cache, "profiles"),
    // Upstream URL for a missing mirror file. A live-boot region's index.html is the host root.
    upstream: (rel) => region.versions.GAME + (region.liveBoot && rel === "index.html" ? "" : rel),
  };
}

const RESOLVED = Object.fromEntries(Object.entries(REGIONS).map(([name, r]) => [name, withPaths(r)]));

function resolveRegion(port) {
  return RESOLVED[PORTS[port] || "vn"];
}

// Region for catalog/battle requests: the server's own non-VN region wins, else ?region=<name>.
function requestRegion(server, query) {
  if (server.name !== "vn") return server;
  const asked = new URLSearchParams(query).get("region");
  return RESOLVED[asked] || server;
}

module.exports = { resolveRegion, requestRegion, REGIONS: RESOLVED };

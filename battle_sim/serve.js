"use strict";
// Serve a mirror (scripts/mirror.js) on localhost with the game host's URL layout.
//   node battle_sim/serve.js [--port 8090] [--ver <ClientVer>] [--fill]
// The region follows the port (lib/serve_region.js): 8090 = VN (default), 8091 = GAT
// (cache .tmp/battle_sim_gat/, newest cached mirror or the live GAT deploy, captures
// events-*.jsonl in that folder; always fills missing static assets from the GAT host).
// Offline by default: a missing file is a 404, printed and appended to misses.log, so the
// gaps show up when the battle page runs. --fill instead downloads the missing file from
// the public game host (same anonymous static GET the mirror uses) and caches it.
const fs = require("fs");
const http = require("http");
const path = require("path");
const { get } = require("./lib/http");
const { liveDeploy } = require("./lib/deploy");
const { resolveRegion, requestRegion } = require("./lib/serve_region");
const capture = require("./lib/capture");
const { readCatalog } = require("./lib/catalogs");

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
  ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".wav": "audio/wav", ".m4a": "audio/mp4",
  ".mp4": "video/mp4", ".ttf": "font/ttf", ".atlas": "text/plain; charset=utf-8",
  ".txt": "text/plain; charset=utf-8", ".bin": "application/octet-stream",
};

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : def;
}

function latestMirror(cache) {
  const dir = path.join(cache, "mirror");
  const vers = fs.existsSync(dir) ? fs.readdirSync(dir).filter((v) => /^\d+$/.test(v)).sort((a, b) => b - a) : [];
  return vers[0] || null;
}

const port = Number(arg("--port", 8090));
const region = resolveRegion(port);
const { versions } = region;
const fill = process.argv.includes("--fill") || region.alwaysFill;
// Live-boot region (GAT): no mirror.js run; the first start writes the live deploy's boot files.
let ver = arg("--ver", null) || latestMirror(region.cache);
if (!ver && !region.liveBoot) throw new Error("no mirror found; run `node battle_sim/scripts/mirror.js fetch` first");
let root = ver && path.join(region.cache, "mirror", ver);
let missLog = root && path.join(root, "misses.log");

// Extra local routes next to the mirror:
//   /sim.html               battle_sim/web/boot.html (the isolated boot page)
//   /__sim/<file>           battle_sim/web/
//   /__sim/configs.json     cached config versions (.tmp/battle_sim/config/)
//   /__sim/deploy.json      the mirror's deploy.json
//   /__sim_config/<ver>/<f> cached config .bin files
//   /__sim_lib/<file>       battle_sim/lib/ (only browser-safe files, e.g. proto_rebuild.js)
//   /__sim/battles.json     captured battles: [{uuid, level, battleType, result, ops}]
//   /__sim/battle/<uuid>.json  one captured battle: {start: StartGameP, quit: QuitRoom}
//   /__sim/setup.html       battle_sim/web/setup.html (profile setup page)
//   /__sim/last-setup.json  last setup saved by `sandbox --setup` (.tmp/battle_sim/profiles/), null if none
const WEB = path.join(__dirname, "web");
const CONFIG = region.configDir;
const LIB = path.join(__dirname, "lib");
const BROWSER_LIB = new Set(["proto_rebuild.js"]);
const PROFILES = region.profilesDir;

function sendJson(res, obj) {
  res.writeHead(200, { "Content-Type": TYPES[".json"], "Cache-Control": "no-cache" }).end(JSON.stringify(obj));
}

// Captured battles, read fresh on each request (captures are small).
function battleRoute(urlPath, reqRegion) {
  if (urlPath === "/__sim/battles.json") {
    return reqRegion.loadBattles().map((b) => {
      const extra = JSON.parse(b.quit.extra || "{}");
      return { uuid: b.start.uuid, level: b.start.level, battleType: b.start.battleType, result: extra.result,
        ops: capture.listItems(b.quit.operations).length, file: path.basename(b.file),
        ...(b.team ? { team: teamSummary(b) } : {}) };
    });
  }
  const m = /^\/__sim\/battle\/([0-9a-f]{24})\.json$/.exec(urlPath);
  if (!m) return undefined;
  const b = reqRegion.loadBattles().find((x) => x.start.uuid === m[1]);
  return b ? { start: b.start, quit: b.quit, ...(b.team ? { team: b.team } : {}) } : null;
}

// Đêm Đỏ capture: per member, master (leaderId) first: name, account fightCap and the summed
// fightCap of the heroes it put in the battle lineup (matched by uuid in its roster).
function teamSummary({ start, team }) {
  const lineup = capture.listItems(capture.listItems(start.playerInfos)[0]?.heros);
  return [...team].sort((a, b) => (b.playerId === Number(start.leaderId)) - (a.playerId === Number(start.leaderId)))
    .map((m) => {
      const own = new Set(capture.listItems(m.heros).map((h) => h.uuid));
      const heroes = lineup.filter((h) => own.has(h.uuid));
      return { playerId: m.playerId, name: m.name, side: m.playerId === Number(start.leaderId) ? "master" : "guest",
        fightCap: m.fightCap, lineupFightCap: heroes.reduce((n, h) => n + (h.fightCap || 0), 0), lineup: heroes.map((h) => h.code) };
    });
}

function within(base, rel) {
  const abs = path.resolve(base, rel);
  return abs.startsWith(path.resolve(base) + path.sep) ? abs : null; // no path traversal
}

function resolve(urlPath) {
  const rel = decodeURIComponent(urlPath.split("?")[0]).replace(/^\/+/, "") || "index.html";
  let abs;
  // The boot page sits at the root so the engine's relative bundle URLs (assets/...) resolve.
  if (rel === "sim.html") abs = path.join(WEB, "boot.html");
  else if (rel === "__sim/deploy.json") abs = path.join(root, "deploy.json");
  else if (rel.startsWith("__sim/")) abs = within(WEB, rel.slice(6));
  else if (rel.startsWith("__sim_config/")) abs = within(CONFIG, rel.slice(13));
  else if (rel.startsWith("__sim_lib/")) abs = BROWSER_LIB.has(rel.slice(10)) ? path.join(LIB, rel.slice(10)) : null;
  else abs = within(root, rel);
  if (!abs) return null;
  return { rel: rel.split(path.sep).join("/"), abs, local: rel.startsWith("__sim") || rel === "sim.html" };
}

// A capture made on an older config (e.g. before a game update) needs that config's .bin files.
// The config CDN keeps old versions, so fetch them on first request, like replay.js does
// (versions.resolveAssets). Public static files, no login; same in offline mode.
async function fetchConfig(rel) {
  const m = /^__sim_config\/([a-z]+_\d+)\/(config|preload_config|lang_([a-z]+))\.bin$/.exec(rel);
  if (!m) return;
  try {
    if (m[3]) await versions.ensureLanguage(m[1], m[3]);
    else await versions.ensureConfig(m[1]);
    console.log("config fetched", rel);
  } catch (e) {
    console.log("config fetch failed", rel, e.message);
  }
}

const server = http.createServer(async (req, res) => {
  const [urlPath, query] = req.url.split("?", 2);
  const reqRegion = requestRegion(region, query);
  const dict = /^\/__sim\/dict\/(hero|support|map|boss|naval-boss|creeps|campaign|blood|antique|relic|artifact|beautybag)-dict\.json$/.exec(urlPath);
  if (region.locale && req.method === "GET" && urlPath === "/__sim/deploy.json") {
    sendJson(res, { ...JSON.parse(fs.readFileSync(path.join(root, "deploy.json"), "utf8")), locale: region.locale });
    return;
  }
  if (reqRegion.name !== "vn" && req.method === "GET" && dict) {
    sendJson(res, readCatalog(dict[1], reqRegion.name));
    return;
  }
  if (urlPath === "/__sim/configs.json") {
    const list = fs.existsSync(CONFIG) ? fs.readdirSync(CONFIG).filter((v) => fs.existsSync(path.join(CONFIG, v, "config.bin"))) : [];
    // Captures made on configs not cached yet (fetched on demand by fetchConfig).
    if (region.liveBoot) for (const b of region.loadBattles()) if (!list.includes(b.start.configVersion)) list.push(b.start.configVersion);
    list.sort((a, b) => Number(b.split("_").pop()) - Number(a.split("_").pop()));
    sendJson(res, list);
    return;
  }
  if (urlPath === "/__sim/last-setup.json") {
    const file = path.join(PROFILES, "last-setup.json");
    sendJson(res, fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : null);
    return;
  }
  const battle = battleRoute(urlPath, reqRegion);
  if (battle !== undefined) {
    if (battle === null) { console.log("404", req.url); res.writeHead(404).end(); return; }
    sendJson(res, battle);
    return;
  }
  const r = resolve(req.url);
  if (!r || req.method !== "GET") {
    res.writeHead(400).end();
    return;
  }
  if (r.local && !fs.existsSync(r.abs)) await fetchConfig(r.rel);
  if (r.local && !fs.existsSync(r.abs)) { console.log("404", r.rel); res.writeHead(404).end(); return; }
  let body = null;
  if (fs.existsSync(r.abs) && fs.statSync(r.abs).isFile()) {
    body = fs.readFileSync(r.abs);
  } else if (fill) {
    try {
      body = await get(region.upstream(r.rel));
      fs.mkdirSync(path.dirname(r.abs), { recursive: true });
      fs.writeFileSync(r.abs, body);
      console.log("fill", r.rel, body.length);
    } catch (e) {
      console.log("fill failed", r.rel, e.message);
    }
  }
  if (!body) {
    console.log("404", r.rel);
    fs.mkdirSync(root, { recursive: true });
    fs.appendFileSync(missLog, `${new Date().toISOString()} ${r.rel}\n`);
    res.writeHead(404, { "Access-Control-Allow-Origin": "*" }).end();
    return;
  }
  res.writeHead(200, {
    "Content-Type": TYPES[path.extname(r.rel).toLowerCase()] || "application/octet-stream",
    "Content-Length": body.length,
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "no-cache",
  });
  res.end(body);
});

async function main() {
  if (region.liveBoot && !ver) {
    const { clientVer, settingsFile, bundleVers, html } = await liveDeploy(region.game);
    ver = clientVer;
    root = path.join(region.cache, "mirror", ver);
    missLog = path.join(root, "misses.log");
    fs.mkdirSync(root, { recursive: true });
    fs.writeFileSync(path.join(root, "index.html"), html);
    fs.writeFileSync(path.join(root, "deploy.json"), JSON.stringify({ clientVer, settingsFile, bundleVers }));
  }
  server.listen(port, "127.0.0.1", () => {
    console.log(`serving mirror ${ver} on http://127.0.0.1:${port}/ (${fill ? "FILL from game host on miss" : "offline, misses -> misses.log"})`);
  });
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});

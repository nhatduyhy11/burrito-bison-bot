"use strict";
// Serve a mirror (scripts/mirror.js) on localhost with the game host's URL layout.
//   node battle_sim/serve.js [--port 8090] [--ver <ClientVer>] [--fill]
// The region follows the port, like in the sandbox: 8090 = VN (default), 8091 = GAT
// (mirror 65985, config trunk_66196; always fills — the first GAT run downloads the
// config, the tw pack and missing static assets).
// Offline by default: a missing file is a 404, printed and appended to misses.log, so the
// gaps show up when the battle page runs. --fill instead downloads the missing file from
// the public game host (same anonymous static GET the mirror uses) and caches it.
const fs = require("fs");
const http = require("http");
const path = require("path");
const { download, get } = require("./lib/http");
const { GAME, liveDeploy } = require("./lib/deploy");
const versions = require("./lib/versions");
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

function latestMirror() {
  const dir = path.join(versions.CACHE, "mirror");
  const vers = fs.existsSync(dir) ? fs.readdirSync(dir).filter((v) => /^\d+$/.test(v)).sort((a, b) => b - a) : [];
  if (!vers.length) throw new Error("no mirror found; run `node battle_sim/scripts/mirror.js fetch` first");
  return vers[0];
}

const port = Number(arg("--port", 8090));
const gat = port === 8091;
const gatRoot = path.join(versions.CACHE, "..", "skin-research-cn");
const gatConfig = "trunk_66196";
const gatConfigFiles = Object.fromEntries(["config", "preload_config", "lang_tw"]
  .map((name) => [`__sim_config/${gatConfig}/${name}.bin`, `${name}.66196.bin`]));
const ver = gat ? "65985" : arg("--ver", null) || latestMirror();
const fill = process.argv.includes("--fill") || gat;
const root = gat ? path.join(gatRoot, "mirror", ver) : path.join(versions.CACHE, "mirror", ver);
const game = gat ? "https://hauntheroesweb.acenetgame.com/" : GAME;
const missLog = path.join(root, "misses.log");

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
const CONFIG = path.join(versions.CACHE, "config");
const LIB = path.join(__dirname, "lib");
const BROWSER_LIB = new Set(["proto_rebuild.js"]);
const PROFILES = path.join(gat ? gatRoot : versions.CACHE, "profiles");

function loadBattles(useGat) {
  if (!useGat) return capture.loadAll();
  if (!fs.existsSync(gatRoot)) return [];
  const files = fs.readdirSync(gatRoot).filter((file) => /^events-pcn-.*\.jsonl$/.test(file));
  return capture.loadAll(files.map((file) => path.join(gatRoot, file)))
    .filter(({ start }) => start.configVersion === gatConfig);
}

function sendJson(res, obj) {
  res.writeHead(200, { "Content-Type": TYPES[".json"], "Cache-Control": "no-cache" }).end(JSON.stringify(obj));
}

// Captured battles, read fresh on each request (captures are small).
function battleRoute(urlPath, useGat) {
  if (urlPath === "/__sim/battles.json") {
    return loadBattles(useGat).map((b) => {
      const extra = JSON.parse(b.quit.extra || "{}");
      return { uuid: b.start.uuid, level: b.start.level, battleType: b.start.battleType, result: extra.result,
        ops: capture.listItems(b.quit.operations).length, file: path.basename(b.file) };
    });
  }
  const m = /^\/__sim\/battle\/([0-9a-f]{24})\.json$/.exec(urlPath);
  if (!m) return undefined;
  const b = loadBattles(useGat).find((x) => x.start.uuid === m[1]);
  return b ? { start: b.start, quit: b.quit } : null;
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
  else if (rel.startsWith("__sim_config/")) {
    if (gat) {
      abs = Object.hasOwn(gatConfigFiles, rel) ? path.join(gatRoot, gatConfigFiles[rel]) : null;
    } else abs = within(CONFIG, rel.slice(13));
  } else if (rel.startsWith("__sim_lib/")) abs = BROWSER_LIB.has(rel.slice(10)) ? path.join(LIB, rel.slice(10)) : null;
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
  const useGatCatalog = gat || new URLSearchParams(query).get("region") === "gat";
  const dict = /^\/__sim\/dict\/(hero|support|map|boss|creeps|campaign|antique|relic|artifact)-dict\.json$/.exec(urlPath);
  if (gat && req.method === "GET" && urlPath === "/__sim/deploy.json") {
    sendJson(res, { ...JSON.parse(fs.readFileSync(path.join(root, "deploy.json"), "utf8")), locale: "tw" });
    return;
  }
  if (useGatCatalog && req.method === "GET" && dict) {
    sendJson(res, readCatalog(dict[1], gatConfig));
    return;
  }
  if (urlPath === "/__sim/configs.json") {
    if (gat) { sendJson(res, [gatConfig]); return; }
    const list = fs.existsSync(CONFIG) ? fs.readdirSync(CONFIG).filter((v) => fs.existsSync(path.join(CONFIG, v, "config.bin"))) : [];
    list.sort((a, b) => Number(b.split("_").pop()) - Number(a.split("_").pop()));
    sendJson(res, list);
    return;
  }
  if (urlPath === "/__sim/last-setup.json") {
    const file = path.join(PROFILES, "last-setup.json");
    sendJson(res, fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : null);
    return;
  }
  const battle = battleRoute(urlPath, useGatCatalog);
  if (battle !== undefined) {
    if (battle === null) { console.log("404", req.url); res.writeHead(404).end(); return; }
    sendJson(res, battle);
    return;
  }
  const r = resolve(req.url);
  if (!r || req.method !== "GET") {
    const missingGatConfig = !r && gat && urlPath.startsWith("/__sim_config/");
    res.writeHead(missingGatConfig ? 404 : 400).end();
    return;
  }
  if (!gat && r.local && !fs.existsSync(r.abs)) await fetchConfig(r.rel);
  if (r.local && !fs.existsSync(r.abs)) { console.log("404", r.rel); res.writeHead(404).end(); return; }
  let body = null;
  if (fs.existsSync(r.abs) && fs.statSync(r.abs).isFile()) {
    body = fs.readFileSync(r.abs);
  } else if (fill) {
    try {
      body = await get(game + (gat && r.rel === "index.html" ? "" : r.rel));
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
  const deployFile = path.join(root, "deploy.json");
  if (gat && !fs.existsSync(deployFile)) {
    const { clientVer, settingsFile, bundleVers, html } = await liveDeploy(game);
    if (clientVer !== ver || bundleVers.main !== "cda14") {
      throw new Error("Live GAT deploy differs from the GAT capture and catalog. Use the matching cached mirror.");
    }
    fs.mkdirSync(root, { recursive: true });
    fs.writeFileSync(path.join(root, "index.html"), html);
    fs.writeFileSync(deployFile, JSON.stringify({ clientVer, settingsFile, bundleVers }));
  }
  if (gat) {
    await Promise.all(Object.values(gatConfigFiles).map((file) =>
      download(`https://cdnres.bighost.games/gat/remoteConfig/trunk/${file}`, path.join(gatRoot, file))));
  }
  server.listen(port, "127.0.0.1", () => {
    console.log(`serving mirror ${ver} on http://127.0.0.1:${port}/ (${fill ? "FILL from game host on miss" : "offline, misses -> misses.log"})`);
  });
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});

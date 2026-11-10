"use strict";
// Serve a mirror (mirror.js) on localhost with the game host's URL layout.
//   node battle_sim/serve.js [--port 8090] [--ver <ClientVer>] [--fill]
// Offline by default: a missing file is a 404, printed and appended to misses.log, so the
// gaps show up when the battle page runs. --fill instead downloads the missing file from
// the public game host (same anonymous static GET the mirror uses) and caches it.
const fs = require("fs");
const http = require("http");
const path = require("path");
const { get } = require("./lib/http");
const { GAME } = require("./lib/deploy");
const versions = require("./lib/versions");

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
  if (!vers.length) throw new Error("no mirror found; run `node battle_sim/mirror.js fetch` first");
  return vers[0];
}

const ver = arg("--ver", null) || latestMirror();
const port = Number(arg("--port", 8090));
const fill = process.argv.includes("--fill");
const root = path.join(versions.CACHE, "mirror", ver);
const missLog = path.join(root, "misses.log");

// Extra local routes next to the mirror:
//   /sim.html               battle_sim/web/boot.html (the isolated boot page)
//   /__sim/<file>           battle_sim/web/
//   /__sim/configs.json     cached config versions (.tmp/battle_sim/config/)
//   /__sim/deploy.json      the mirror's deploy.json
//   /__sim_config/<ver>/<f> cached config .bin files
const WEB = path.join(__dirname, "web");
const CONFIG = path.join(versions.CACHE, "config");

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
  else abs = within(root, rel);
  if (!abs) return null;
  return { rel: rel.split(path.sep).join("/"), abs, local: rel.startsWith("__sim") || rel === "sim.html" };
}

const server = http.createServer(async (req, res) => {
  if (req.url.split("?")[0] === "/__sim/configs.json") {
    const list = fs.existsSync(CONFIG) ? fs.readdirSync(CONFIG).filter((v) => fs.existsSync(path.join(CONFIG, v, "config.bin"))) : [];
    list.sort((a, b) => Number(b.split("_").pop()) - Number(a.split("_").pop()));
    res.writeHead(200, { "Content-Type": TYPES[".json"], "Cache-Control": "no-cache" }).end(JSON.stringify(list));
    return;
  }
  const r = resolve(req.url);
  if (!r || req.method !== "GET") { res.writeHead(400).end(); return; }
  if (r.local && !fs.existsSync(r.abs)) { console.log("404", r.rel); res.writeHead(404).end(); return; }
  let body = null;
  if (fs.existsSync(r.abs) && fs.statSync(r.abs).isFile()) {
    body = fs.readFileSync(r.abs);
  } else if (fill) {
    try {
      body = await get(GAME + r.rel);
      fs.mkdirSync(path.dirname(r.abs), { recursive: true });
      fs.writeFileSync(r.abs, body);
      console.log("fill", r.rel, body.length);
    } catch (e) {
      console.log("fill failed", r.rel, e.message);
    }
  }
  if (!body) {
    console.log("404", r.rel);
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

server.listen(port, "127.0.0.1", () => {
  console.log(`serving mirror ${ver} on http://127.0.0.1:${port}/ (${fill ? "FILL from game host on miss" : "offline, misses -> misses.log"})`);
});

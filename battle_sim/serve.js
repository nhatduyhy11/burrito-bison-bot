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

function resolve(urlPath) {
  const rel = decodeURIComponent(urlPath.split("?")[0]).replace(/^\/+/, "") || "index.html";
  const abs = path.resolve(root, rel);
  if (!abs.startsWith(path.resolve(root) + path.sep)) return null; // no path traversal
  return { rel: rel.split(path.sep).join("/"), abs };
}

const server = http.createServer(async (req, res) => {
  const r = resolve(req.url);
  if (!r || req.method !== "GET") { res.writeHead(400).end(); return; }
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

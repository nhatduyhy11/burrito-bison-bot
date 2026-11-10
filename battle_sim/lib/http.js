"use strict";
// Minimal HTTPS GET (Node's TLS stack; Windows curl/schannel fails revocation
// checks on the bighost CDN).
const fs = require("fs");
const https = require("https");
const path = require("path");

function get(url, redirects = 5) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { "User-Agent": "Mozilla/5.0" } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location && redirects > 0) {
        res.resume();
        resolve(get(new URL(res.headers.location, url).toString(), redirects - 1));
        return;
      }
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => {
        const body = Buffer.concat(chunks);
        if (res.statusCode !== 200) reject(new Error(`HTTP ${res.statusCode} ${url}`));
        else resolve(body);
      });
    }).on("error", (e) => reject(new Error(`${e.message} ${url}`)));
  });
}

async function getText(url) { return (await get(url)).toString("utf8"); }
async function getJson(url) { return JSON.parse(await getText(url)); }

// Download to dest unless it already exists. Writes via a temp file so an
// interrupted download never leaves a truncated cache entry.
async function download(url, dest) {
  if (fs.existsSync(dest)) return false;
  const body = await get(url);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest + ".part", body);
  fs.renameSync(dest + ".part", dest);
  return true;
}

module.exports = { get, getText, getJson, download };

"use strict";
// Captured battles from the research hook's event logs (.tmp/battle_research/events-*.jsonl).
// A battle = the room-socket StartGameP push .. the QuitRoom request sent at the end.
const fs = require("fs");
const path = require("path");

const CAPTURE_DIR = path.join(__dirname, "..", "..", ".tmp", "battle_research");

function listItems(j) {
  if (!j) return [];
  const n = j._length != null ? j._length : 0;
  return Array.from({ length: n }, (_, i) => j[String(i)]);
}

// Battles (StartGameP .. QuitRoom) in one capture file.
function loadCapture(file) {
  const lines = fs.readFileSync(file, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
  const battles = [];
  let cur = null;
  for (const e of lines) {
    const msg = e.data && typeof e.data === "object" ? String(e.data.msg || "") : "";
    if (e.kind === "room" && msg.includes("StartGameP")) { cur = { file, start: e.data.obj, events: [] }; battles.push(cur); continue; }
    if (!cur) continue;
    cur.events.push(e);
    if (e.kind === "sock" && msg.includes("QuitRoom(")) cur.quit = e.data.obj;
  }
  return battles.filter((b) => b.quit);
}

function captureFiles() {
  try {
    return fs.readdirSync(CAPTURE_DIR).filter((f) => /^events-.*\.jsonl$/.test(f)).map((f) => path.join(CAPTURE_DIR, f));
  } catch { return []; }
}

// Every complete battle across the given files (default: all captures), first one per uuid.
function loadAll(files = captureFiles()) {
  const byUuid = new Map();
  for (const f of files) for (const b of loadCapture(f)) if (!byUuid.has(b.start.uuid)) byUuid.set(b.start.uuid, b);
  return [...byUuid.values()];
}

module.exports = { CAPTURE_DIR, listItems, loadCapture, captureFiles, loadAll };

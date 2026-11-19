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

// Team battles (Đêm Đỏ, battleType 47/48): the lobby push refreshMemberInfosR carries each
// member's full hero roster and account fightCap. It never reaches the battle; the setup page and
// the profile engine use it to know who owns which hero (docs/planning/blood_night_setup.md).
const TEAM_BATTLE_TYPES = new Set([47, 48]);
const teamMember = ({ baseInfo, moduleDatas }) => ({
  playerId: Number(baseInfo.playerId), name: baseInfo.name, fightCap: baseInfo.fightCap, heros: moduleDatas.heros,
});

// Battles (StartGameP .. QuitRoom) in one capture file.
function loadCapture(file) {
  const lines = fs.readFileSync(file, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
  const battles = [];
  let cur = null;
  let team = null; // latest refreshMemberInfosR members
  for (const e of lines) {
    const msg = e.data && typeof e.data === "object" ? String(e.data.msg || "") : "";
    if (e.kind === "sock" && msg.includes("refreshMemberInfosR(") && e.data.obj?.members) {
      team = listItems(e.data.obj.members).map(teamMember);
    }
    if (e.kind === "room" && msg.includes("StartGameP")) {
      const start = e.data.obj;
      cur = { file, start, events: [] };
      const ids = listItems(start.playerInfos).map((p) => Number(p.playerId));
      if (TEAM_BATTLE_TYPES.has(start.battleType) && team && ids.every((id) => team.some((m) => m.playerId === id))) {
        cur.team = team;
      }
      battles.push(cur);
      continue;
    }
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

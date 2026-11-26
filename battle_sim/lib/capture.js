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
// derma = the worn Summoner skin (model only; StartGameP does not carry it).
const teamMember = ({ baseInfo, moduleDatas }) => ({
  playerId: Number(baseInfo.playerId), name: baseInfo.name, fightCap: baseInfo.fightCap, derma: baseInfo.derma || 0,
  heros: moduleDatas.heros,
});

// Solo roster gear: the lobby cache (HeroRosterSnapshot) has no per-hero relic/artifact. The login
// responses GetRelicInfoR / GetArtifactInfoR (this account only) carry wearList = item uuid -> heroUuid
// plus the item lists, so each roster hero gets them in the battle lineup's shape: relic = relic code,
// artifact = {uuid, code, battleEntryInfos?}. A hero with no wearList entry wears nothing. Without a
// response the field stays missing and is kept in incompleteFields (not guessed). They arrive at login
// only and not in every session.
function enrichRoster(roster, gear) {
  const heros = listItems(roster.heros);
  const wornBy = (resp, items) => {
    const byUuid = new Map(listItems(resp[items]).map((it) => [it.uuid, it]));
    return new Map(listItems(resp.wearList).map((w) => [w.heroUuid, byUuid.get(w.uuid)]).filter(([, it]) => it));
  };
  const filled = [];
  if (gear.relic) {
    const worn = wornBy(gear.relic, "relicList");
    for (const h of heros) if (worn.has(h.uuid)) h.relic = worn.get(h.uuid).code;
    filled.push("relic");
  }
  if (gear.artifact) {
    const worn = wornBy(gear.artifact, "artifactList");
    for (const h of heros) {
      const it = worn.get(h.uuid);
      if (it) h.artifact = { uuid: it.uuid, code: it.code, ...(listItems(it.battleEntryInfos).length ? { battleEntryInfos: it.battleEntryInfos } : {}) };
    }
    filled.push("artifact");
  }
  if (!filled.length) return roster;
  const incompleteFields = (roster.incompleteFields || []).filter((f) => !filled.includes(f));
  return { ...roster, incompleteFields, complete: incompleteFields.length === 0, gearFrom: filled.map((f) => `${f}:wearList`) };
}

// Battles (StartGameP .. QuitRoom) in one capture file. Each battle also carries `pre`: the
// lobby events recorded since the previous battle ended (enter payloads, roster pushes,
// artifact responses, the previous battle's reward response).
function loadCapture(file) {
  const lines = fs.readFileSync(file, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
  const battles = [];
  let cur = null;
  let team = null; // latest refreshMemberInfosR members
  let roster = null; // explicit passive snapshot of this account, before StartGameP
  let pre = []; // lobby events outside or after a battle
  const gear = {}; // latest GetRelicInfoR / GetArtifactInfoR responses
  for (const e of lines) {
    const msg = e.data && typeof e.data === "object" ? String(e.data.msg || "") : "";
    if (e.kind === "sock" && e.data.obj?.wearList && !e.data.obj.err) {
      if (msg.includes("GetRelicInfoR(")) gear.relic = e.data.obj;
      if (msg.includes("GetArtifactInfoR(")) gear.artifact = e.data.obj;
    }
    if (e.kind === "sock" && msg.includes("refreshMemberInfosR(") && e.data.obj?.members) {
      team = listItems(e.data.obj.members).map(teamMember);
    }
    if (e.kind === "roster" && msg === "HeroRosterSnapshot" && e.data.obj?.heros) {
      roster = e.data.obj;
    }
    if (e.kind === "room" && msg.includes("StartGameP")) {
      const start = e.data.obj;
      cur = { file, start, pre, events: [] };
      pre = [];
      const ids = listItems(start.playerInfos).map((p) => Number(p.playerId));
      const main = team?.find((m) => m.playerId === ids[0]);
      if (main) cur.roster = { playerId: main.playerId, heros: main.heros, source: "team", complete: true };
      else if (roster && Number(roster.playerId) === ids[0]) cur.roster = enrichRoster(JSON.parse(JSON.stringify(roster)), gear);
      if (TEAM_BATTLE_TYPES.has(start.battleType) && team && ids.every((id) => team.some((m) => m.playerId === id))) {
        cur.team = team;
      }
      battles.push(cur);
      continue;
    }
    if (!cur || cur.quit) {
      pre.push(e);
      continue;
    }
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

"use strict";
// Tier-2 checkpoints: structured mid-battle facts recorded in the sim, and the
// same facts extracted from a research-hook capture, so the two can be diffed.

function installRecorders(sim) {
  const rec = { random: [], waves: null, bossKills: [] };
  const req = sim.req;
  const P = req("TDPlayerEntity").TDPlayerEntity.prototype;
  const origRandom = P.randomCode;
  P.randomCode = function (types, num, mode, elite, ...rest) {
    const r = origRandom.call(this, types, num, mode, elite, ...rest);
    const list = elite ? this._lotteryEliteCodes : this._lotteryCodes;
    rec.random.push({ frame: sim.td.curFrame, mode, elite: !!elite, result: (list || []).slice() });
    return r;
  };
  const td = sim.td;
  const origCommit = td.commitInfoToDelegate;
  // Recorders must never change control flow: snapshot before, never throw.
  td.commitInfoToDelegate = function (op) {
    let snap = null;
    if (op && op.waveSchedules && !rec.waves) {
      try { snap = normWaves(op.waveSchedules, (l) => sim.rb.listItems(l)); } catch (e) { rec.wavesError = String(e); }
    }
    const r = origCommit.call(this, op);
    if (snap) rec.waves = snap;
    return r;
  };
  const d = sim.delegate;
  const origLog = d.log;
  d.log = function (...a) {
    const s = a.filter((x) => typeof x === "string").join(" ");
    const m = /Boss_(\d+)\S*?(\d+)\s/.exec(s);
    if (s.includes("Boss_") && s.includes("被击杀帧数")) {
      const mm = /Boss_(\d+).*?：(\d+)/.exec(s);
      if (mm) rec.bossKills.push({ entityId: Number(mm[1]), tick: Number(mm[2]) });
    }
    return origLog.apply(this, a);
  };
  return rec;
}

// creepSchedule(Dictionary frame -> List<info>) -> sorted [[frame, code, x, y, roundCode]]
function normWaves(ws, listItems) {
  const out = [];
  ws.forEach((w) => {
    const cs = w.creepSchedule;
    const keys = cs.getKeys(false), vals = cs.getValues(false);
    for (let i = 0; i < keys.length; i++) {
      vals[i].forEach((it) => out.push([Number(keys[i]), it.code, it.x, it.y, it.roundCode]));
    }
  });
  out.sort((a, b) => a[0] - b[0] || a[4] - b[4] || a[1] - b[1] || a[2] - b[2] || a[3] - b[3]);
  return out;
}

function listItemsJson(j) {
  if (!j) return [];
  if (Array.isArray(j)) return j;
  const n = j._length != null ? j._length : 0;
  return Array.from({ length: n }, (_, i) => j[String(i)]);
}

// Same facts from the capture's event stream (events after StartGameP).
function fromCapture(events) {
  const rec = { random: [], waves: null, bossKills: [] };
  for (const e of events) {
    if (e.kind === "rng.randomCode") {
      rec.random.push({ frame: e.data.frame, mode: e.data.mode, elite: !!e.data.elite, result: e.data.result });
    } else if (e.kind === "td.oper" && e.data && e.data.waveSchedules && !rec.waves) {
      const ws = e.data.waveSchedules;
      const out = [];
      listItemsJson(ws).forEach((w) => {
        const cs = w.creepSchedule || {};
        for (const k of Object.keys(cs)) {
          if (k.startsWith("_")) continue;
          listItemsJson(cs[k]).forEach((it) => out.push([Number(k), it.code, it.x, it.y, it.roundCode]));
        }
      });
      out.sort((a, b) => a[0] - b[0] || a[4] - b[4] || a[1] - b[1] || a[2] - b[2] || a[3] - b[3]);
      rec.waves = out;
    } else if (e.kind === "eng.log") {
      const s = (e.data.a || []).join(" ");
      const mm = /Boss_(\d+).*?：(\d+)/.exec(s);
      if (mm && s.includes("被击杀帧数")) rec.bossKills.push({ entityId: Number(mm[1]), tick: Number(mm[2]) });
    }
  }
  return rec;
}

function compare(game, sim) {
  const lines = [];
  let ok = true;
  // waves
  if (game.waves) {
    const a = JSON.stringify(game.waves), b = JSON.stringify(sim.waves);
    const same = a === b;
    ok = ok && same;
    lines.push(`tier2 ${same ? "OK  " : "DIFF"} waveSchedule: ${game.waves.length} spawns${same ? "" : ` (sim ${sim.waves ? sim.waves.length : 0})`}`);
    if (!same && sim.waves) {
      const i = game.waves.findIndex((x, k) => JSON.stringify(x) !== JSON.stringify(sim.waves[k]));
      lines.push(`      first diff #${i}: game ${JSON.stringify(game.waves[i])} sim ${JSON.stringify(sim.waves[i])}`);
    }
  } else lines.push("tier2 --   waveSchedule: not in capture");
  // random draws (summon options + spins)
  if (game.random.length) {
    let n = 0, firstBad = null;
    game.random.forEach((g, i) => {
      const s = sim.random[i];
      const same = s && s.frame === g.frame && s.elite === g.elite && JSON.stringify(s.result) === JSON.stringify(g.result);
      if (same) n++; else if (!firstBad) firstBad = { i, g, s };
    });
    const same = n === game.random.length && sim.random.length === game.random.length;
    ok = ok && same;
    lines.push(`tier2 ${same ? "OK  " : "DIFF"} randomCode: ${n}/${game.random.length} match (sim calls ${sim.random.length})`);
    if (firstBad) lines.push(`      first diff #${firstBad.i}: game ${JSON.stringify(firstBad.g)} sim ${JSON.stringify(firstBad.s)}`);
  } else lines.push("tier2 --   randomCode: not in capture");
  // boss kills
  if (game.bossKills.length) {
    const a = JSON.stringify(game.bossKills), b = JSON.stringify(sim.bossKills);
    const same = a === b;
    ok = ok && same;
    lines.push(`tier2 ${same ? "OK  " : "DIFF"} bossKills: game ${a}${same ? "" : " sim " + b}`);
  } else lines.push("tier2 --   bossKills: not in capture");
  return { ok, lines };
}

module.exports = { installRecorders, fromCapture, compare };

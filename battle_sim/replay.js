"use strict";
// Replay a captured battle headlessly and compare with what the game reported.
//   node battle_sim/replay.js <capture.jsonl> [uuid]
// capture.jsonl = research-hook event log containing StartGameP + QuitRoom.
const fs = require("fs");
const path = require("path");
const { Sim } = require("./lib/sim");
const checkpoints = require("./lib/checkpoints");

const root = path.join(__dirname, "..");
const DATA = path.join(root, ".tmp/battle_research/data");

function listItems(j) {
  if (!j) return [];
  const n = j._length != null ? j._length : 0;
  return Array.from({ length: n }, (_, i) => j[String(i)]);
}

function loadCapture(file, wantUuid) {
  const lines = fs.readFileSync(file, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
  const battles = [];
  let cur = null;
  for (const e of lines) {
    const msg = e.data && typeof e.data === "object" ? String(e.data.msg || "") : "";
    if (e.kind === "room" && msg.includes("StartGameP")) { cur = { start: e.data.obj, events: [] }; battles.push(cur); continue; }
    if (!cur) continue;
    cur.events.push(e);
    if (e.kind === "sock" && msg.includes("QuitRoom(")) cur.quit = e.data.obj;
  }
  const b = wantUuid ? battles.find((x) => x.start.uuid === wantUuid) : battles.filter((x) => x.quit).pop();
  if (!b) throw new Error("battle not found in capture");
  return b;
}

async function main() {
  const file = process.argv[2];
  const battle = loadCapture(file, process.argv[3]);
  const ops = listItems(battle.quit.operations);
  const extra = JSON.parse(battle.quit.extra);
  console.log(`battle ${battle.start.uuid} level ${battle.start.level}: ${ops.length} ops, game result ${extra.result} ${extra.resultReason} endFrame ${battle.quit.endFrame}`);

  const t0 = Date.now();
  const sim = new Sim({
    bundle: path.join(root, ".tmp/bundle/main.1377a/index.1377a.js"),
    config: path.join(DATA, "config.65380.bin"),
    preloadConfig: path.join(DATA, "preload_config.65380.bin"),
    mapsDir: path.join(DATA, "maps"),
  });
  console.log("loaded in", Date.now() - t0, "ms; map", sim.setup(battle.start));
  const rec = checkpoints.installRecorders(sim);
  await sim.start();
  const t1 = Date.now();
  const maxTick = Number(process.env.MAX_TICK || 6000);
  let lastLog = Date.now();
  const { applied, remaining } = sim.run(ops, {
    maxTick,
    onTick: (s) => {
      if (Date.now() - lastLog > 5000) {
        lastLog = Date.now();
        console.log(`  ... tick ${s.tick} (${((Date.now() - t1) / 1000).toFixed(0)}s)`);
      }
    },
  });
  const st = sim.delegate._battleStatistics;
  const fails = applied.filter((a) => !a.r || !a.r.success);
  console.log(`sim ran ${sim.tick} ticks in ${Date.now() - t1} ms; ops applied ${applied.length}, failed ${fails.length}, not reached ${remaining.length}`);
  fails.slice(0, 10).forEach((f) => console.log("  fail", f.tick, f.op.operationType, f.op.playerId, f.op.args, f.r && f.r.error ? f.r.error.split("\n")[0] : ""));
  if (fails[0] && fails[0].r && fails[0].r.error) console.log("first error:\n" + fails[0].r.error.split("\n").slice(0, 8).join("\n"));
  console.log("sim result", st && st.result, st && st.resultReason);

  // Tier 1: compare the upload ext (what the game sends in QuitRoom.extra).
  const myPid = battle.start.playerInfos["0"].playerId;
  const me = sim.td.getPlayerEntity ? sim.td.getPlayerEntity(myPid) : null;
  const myCamp = me ? me.campId : 1;
  const simExt = JSON.parse(JSON.stringify(st.getUploadExt(myCamp)));
  const keys = [...new Set([...Object.keys(extra), ...Object.keys(simExt)])].filter((k) => k !== "fightCap");
  let ok = true;
  // On a loss the game sends endFrame 0; fall back to totalTime (seconds).
  const endOk = battle.quit.endFrame ? battle.quit.endFrame === sim.tick : Math.floor(sim.tick / 10) === battle.quit.totalTime;
  console.log(`tier1 ${endOk ? "OK  " : "DIFF"} end: game endFrame ${battle.quit.endFrame} totalTime ${battle.quit.totalTime}, sim tick ${sim.tick}`);
  for (const k of keys) {
    const a = JSON.stringify(extra[k]), b = JSON.stringify(simExt[k]);
    const same = a === b;
    ok = ok && same;
    console.log(`tier1 ${same ? "OK  " : "DIFF"} ${k}: game=${(a || "").slice(0, 160)}${same ? "" : "  sim=" + (b || "").slice(0, 160)}`);
  }
  console.log("TIER1", ok && endOk ? "MATCH" : "MISMATCH");
  const t2 = checkpoints.compare(checkpoints.fromCapture(battle.events), rec);
  t2.lines.forEach((l) => console.log(l));
  console.log("TIER2", t2.ok ? "MATCH" : "MISMATCH");
  fs.writeFileSync(path.join(DATA, `simlog-${battle.start.uuid}.json`), JSON.stringify(sim.gameLog.slice(0, 20000), null, 0));
}

main().catch((e) => { console.error(e && e.stack || e); process.exit(1); });

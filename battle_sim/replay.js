"use strict";
// Replay captured battles headlessly and compare with what the game reported.
//   node battle_sim/replay.js                              # every battle in .tmp/battle_research/events-*.jsonl
//   node battle_sim/replay.js <capture.jsonl>... [uuid] [-v]
// capture.jsonl = research-hook event log containing StartGameP + QuitRoom.
// Bundle / config / maps are picked from the battle's own StartGameP versions
// (lib/versions.js); a missing config is downloaded, missing bundle/maps is an error.
const fs = require("fs");
const path = require("path");
const { Sim } = require("./lib/sim");
const checkpoints = require("./lib/checkpoints");
const versions = require("./lib/versions");
const { listItems, loadAll } = require("./lib/capture");

const root = path.join(__dirname, "..");

async function replayBattle(battle) {
  const start = battle.start;
  const ops = listItems(battle.quit.operations);
  const extra = JSON.parse(battle.quit.extra);
  const lines = [];
  const out = (l) => lines.push(l);
  out(`battle ${start.uuid} level ${start.level}: ${ops.length} ops, game result ${extra.result} ${extra.resultReason} endFrame ${battle.quit.endFrame}`);

  const t0 = Date.now();
  const assets = await versions.resolveAssets(start);
  const sim = new Sim(assets);
  // Versions the sim really runs with must equal the ones the game reported.
  const loaded = versions.loadedVersions(sim);
  let verOk = true;
  for (const k of ["battleVersion", "configVersion", "mapVersion"]) {
    const same = loaded[k] === start[k];
    verOk = verOk && same;
    out(`ver   ${same ? "OK  " : "DIFF"} ${k}: game=${start[k]}${same ? "" : "  sim=" + loaded[k]}`);
  }
  const map = sim.setup(start);
  out(`loaded in ${Date.now() - t0} ms; map ${map.tiledBg} (bg ${map.bgId}); bundle ${path.relative(root, assets.bundle)}`);
  const rec = checkpoints.installRecorders(sim);
  await sim.start();
  const t1 = Date.now();
  const maxTick = Number(process.env.MAX_TICK || 6000);
  const { applied, remaining } = sim.run(ops, { maxTick });
  const st = sim.delegate._battleStatistics;
  const fails = applied.filter((a) => !a.r || !a.r.success);
  out(`sim ran ${sim.tick} ticks in ${Date.now() - t1} ms; ops applied ${applied.length}, failed ${fails.length}, not reached ${remaining.length}`);
  fails.slice(0, 10).forEach((f) => out(`  fail ${f.tick} ${f.op.operationType} ${f.op.playerId} ${f.op.args} ${f.r && f.r.error ? f.r.error.split("\n")[0] : ""}`));
  if (fails[0] && fails[0].r && fails[0].r.error) out("first error:\n" + fails[0].r.error.split("\n").slice(0, 8).join("\n"));
  out(`sim result ${st && st.result} ${st && st.resultReason}`);

  // Tier 1: compare the upload ext (what the game sends in QuitRoom.extra).
  const myPid = start.playerInfos["0"].playerId;
  const me = sim.td.getPlayerEntity ? sim.td.getPlayerEntity(myPid) : null;
  const myCamp = me ? me.campId : 1;
  const simExt = JSON.parse(JSON.stringify(st.getUploadExt(myCamp)));
  const keys = [...new Set([...Object.keys(extra), ...Object.keys(simExt)])].filter((k) => k !== "fightCap");
  // On a loss the game sends endFrame 0; fall back to totalTime (seconds).
  const endOk = battle.quit.endFrame ? battle.quit.endFrame === sim.tick : Math.floor(sim.tick / 10) === battle.quit.totalTime;
  let t1ok = endOk;
  out(`tier1 ${endOk ? "OK  " : "DIFF"} end: game endFrame ${battle.quit.endFrame} totalTime ${battle.quit.totalTime}, sim tick ${sim.tick}`);
  for (const k of keys) {
    const a = JSON.stringify(extra[k]), b = JSON.stringify(simExt[k]);
    const same = a === b;
    t1ok = t1ok && same;
    out(`tier1 ${same ? "OK  " : "DIFF"} ${k}: game=${(a || "").slice(0, 160)}${same ? "" : "  sim=" + (b || "").slice(0, 160)}`);
  }
  out(`TIER1 ${t1ok ? "MATCH" : "MISMATCH"}`);
  const t2 = checkpoints.compare(checkpoints.fromCapture(battle.events), rec);
  t2.lines.forEach(out);
  out(`TIER2 ${t2.ok ? "MATCH" : "MISMATCH"}`);
  fs.mkdirSync(versions.CACHE, { recursive: true });
  fs.writeFileSync(path.join(versions.CACHE, `simlog-${start.uuid}.json`), JSON.stringify(sim.gameLog.slice(0, 20000), null, 0));
  return { ok: verOk && t1ok && t2.ok, verOk, t1ok, t2ok: t2.ok, lines, ticks: sim.tick };
}

async function main() {
  const args = process.argv.slice(2);
  const verbose = args.includes("-v");
  const uuids = args.filter((a) => /^[0-9a-f]{24}$/.test(a));
  const files = args.filter((a) => a !== "-v" && !uuids.includes(a));
  let battles = loadAll(files.length ? files : undefined);
  if (uuids.length) battles = battles.filter((b) => uuids.includes(b.start.uuid));
  if (!battles.length) throw new Error("no battle with StartGameP + QuitRoom found");
  const detail = verbose || battles.length === 1;

  const results = [];
  for (const b of battles) {
    let r;
    try {
      r = await replayBattle(b);
    } catch (e) {
      r = { ok: false, error: String(e && e.message || e), lines: [`battle ${b.start.uuid}: ERROR ${e && e.stack || e}`] };
    }
    results.push({ b, r });
    // Batch mode: full detail only for battles that don't match.
    const show = detail || !r.ok ? r.lines : r.lines.filter((l) => !/^(ver|tier[12]) +OK/.test(l));
    show.forEach((l) => console.log(l));
    console.log("");
  }
  if (results.length > 1) {
    console.log("summary:");
    for (const { b, r } of results) {
      const st = r.error ? `ERROR ${r.error.split("\n")[0]}` : `ver ${r.verOk ? "ok" : "DIFF"} tier1 ${r.t1ok ? "ok" : "DIFF"} tier2 ${r.t2ok ? "ok" : "DIFF"}`;
      console.log(`  ${r.ok ? "MATCH   " : "MISMATCH"} ${b.start.uuid} L${b.start.level} ${b.start.battleVersion} ${b.start.configVersion} ${b.start.mapVersion}  ${st}  (${path.basename(b.file)})`);
    }
  }
  const bad = results.filter((x) => !x.r.ok).length;
  console.log(`${results.length - bad}/${results.length} battles match`);
  process.exit(bad ? 1 : 0);
}

main().catch((e) => { console.error(e && e.stack || e); process.exit(1); });

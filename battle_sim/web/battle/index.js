// Entry of the battle view: open a captured battle in the isolated page and replay its op log
// with the game's own battle view. boot.js imports this module and calls runBattle after boot.
// profile.js (with map-profile, build-skin-profile and hero/) is imported only with ?play&profile.
//
// Entry point is the same one the room socket uses: TDModule.onStartGamePPush(StartGameP).
// Everything that would reach a server is stubbed in this page only (stubs.js).
// ?play: no op log. The player uses the battle UI; ops take the game's own Local path.
// ?seed=random|<uuid> changes the RNG seed.
import { compareQuit, installReplay } from "./replay.js";
import { ensureBattleConfig, initModules, setupMain } from "./setup.js";
import { captureErrors, leaveOnResultClose, stubNetwork, stubPause, stubQuitRoom, unlockMonthCards } from "./stubs.js";

export async function runBattle({ sim, step, R }) {
  const M = (name) => R(name)[name];
  const params = new URLSearchParams(location.search);
  // ?play: the player drives the battle through the game's own UI (no op log). Ops take the
  // game's normal Local path (TDServerProxy.commitClientRequest -> TDServer.handleClientRequest),
  // robots are run by the director, and the director pauses on blocking panels as in the game.
  const play = params.has("play");
  const { quit } = sim.capture;
  // StartGameP.uuid seeds the battle RNG: same uuid = same battle as the capture.
  // ?seed=random (or any 24-hex string) starts a different battle with the same account data.
  const start = { ...sim.capture.start, uuid: pickSeed(params.get("seed"), sim.capture.start.uuid) };
  const rb = window.makeRebuilder(R);
  let summonerDerma = 0;
  if (play && params.has("profile")) {
    const { applyProfile } = await import("./profile.js");
    ({ summonerDerma } = await applyProfile(start, rb, M, step));
  }
  const s2c = rb.build("StartGameP_BuildRoom_S2C", start);
  const ops = play ? [] : rb.listItems(quit.operations).slice().sort((a, b) => a.operFrame - b.operFrame || a.index - b.index);
  const myPid = rb.listItems(start.playerInfos)[0].playerId;
  if (play) window.__simPlayedStart = start; // sandbox saves it with the QuitRoom (not polled: ~24KB)
  const report = (sim.battle = {
    mode: play ? "play" : "replay", uuid: start.uuid, capturedUuid: sim.capture.start.uuid, myPid,
    ops: ops.length, applied: 0, failed: [], dropped: [], foreignOps: 0, netCalls: [], tick: 0, quit: null,
  });
  const ctx = { M, R, report, step };

  captureErrors(ctx);
  setupMain(ctx);
  stubNetwork({ ...ctx, myPid, summonerDerma });
  initModules(ctx);
  if (play) unlockMonthCards(ctx);
  stubQuitRoom({ ...ctx, rb, play, onQuit: finish });
  stubPause(ctx);
  if (play) leaveOnResultClose(ctx);
  installReplay({ ...ctx, ops, play, myPid, start });
  ensureBattleConfig({ ...ctx, battleType: start.battleType });

  // --- Enter the battle exactly like the room socket's StartGameP push ---
  let done = false;
  function finish() {
    if (done) return;
    done = true;
    const TDServer = M("TDServer").Ins;
    const st = TDServer._delegate && TDServer._delegate._battleStatistics;
    report.result = st && { result: st.result, resultReason: st.resultReason };
    if (play) {
      step("battle end", { tick: report.tick, ops: report.quit.operations.length, extra: report.quit.extra && JSON.parse(report.quit.extra) });
    } else {
      report.compare = compareQuit(quit, report.quit);
      step("battle end", { tick: report.tick, applied: report.applied, failed: report.failed.length, dropped: report.dropped.length, match: report.compare.ok });
    }
    sim.state = "done";
  }
  await M("TDModule").Ins.onStartGamePPush(s2c);
  step("StartGameP pushed", { uuid: start.uuid, level: start.level, battleType: start.battleType });
}

// Battle uuid (= RNG seed): ?seed absent -> the captured one; "random" -> fresh 24-hex
// (same shape as a server uuid); anything else is used as given.
function pickSeed(seed, captured) {
  if (!seed) return captured;
  if (seed !== "random") return seed;
  const b = new Uint8Array(12);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

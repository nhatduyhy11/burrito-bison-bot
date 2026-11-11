// Entry of the battle view: open a captured battle in the isolated page and replay its op log
// with the game's own battle view. boot.js loads the other files of this folder first
// (stubs, setup, replay; profile + skin-profile with ?profile), then this one, and calls
// window.__simBattle after boot.
//
// Entry point is the same one the room socket uses: TDModule.onStartGamePPush(StartGameP).
// Everything that would reach a server is stubbed in this page only (stubs.js).
// ?play: no op log. The player uses the battle UI; ops take the game's own Local path.
// ?seed=random|<uuid> changes the RNG seed.
(function () {
  "use strict";
  const SimBattle = window.SimBattle;

  window.__simBattle = async function ({ sim, step, R }) {
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
    if (play && params.has("profile")) {
      await SimBattle.applyProfile(start, rb, M, step);
    }
    const s2c = rb.build("StartGameP_BuildRoom_S2C", start);
    const ops = play ? [] : rb.listItems(quit.operations).slice().sort((a, b) => a.operFrame - b.operFrame || a.index - b.index);
    const myPid = rb.listItems(start.playerInfos)[0].playerId;
    if (play) window.__simPlayedStart = start; // sandbox.py saves it with the QuitRoom (not polled: ~24KB)
    const report = (sim.battle = {
      mode: play ? "play" : "replay", uuid: start.uuid, capturedUuid: sim.capture.start.uuid, myPid,
      ops: ops.length, applied: 0, failed: [], dropped: [], foreignOps: 0, netCalls: [], tick: 0, quit: null,
    });
    const ctx = { M, R, report, step };

    SimBattle.captureErrors(ctx);
    SimBattle.setupMain(ctx);
    SimBattle.stubNetwork({ ...ctx, myPid });
    SimBattle.initModules(ctx);
    if (play) SimBattle.unlockMonthCards(ctx);
    SimBattle.stubQuitRoom({ ...ctx, rb, play, onQuit: finish });
    SimBattle.stubPause(ctx);
    if (play) SimBattle.leaveOnResultClose(ctx);
    SimBattle.installReplay({ ...ctx, ops, play, myPid, start });
    SimBattle.ensureBattleConfig({ ...ctx, battleType: start.battleType });

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
        report.compare = SimBattle.compareQuit(quit, report.quit);
        step("battle end", { tick: report.tick, applied: report.applied, failed: report.failed.length, dropped: report.dropped.length, match: report.compare.ok });
      }
      sim.state = "done";
    }
    await M("TDModule").Ins.onStartGamePPush(s2c);
    step("StartGameP pushed", { uuid: start.uuid, level: start.level, battleType: start.battleType });
  };

  // Battle uuid (= RNG seed): ?seed absent -> the captured one; "random" -> fresh 24-hex
  // (same shape as a server uuid); anything else is used as given.
  function pickSeed(seed, captured) {
    if (!seed) return captured;
    if (seed !== "random") return seed;
    const b = new Uint8Array(12);
    crypto.getRandomValues(b);
    return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  }
})();

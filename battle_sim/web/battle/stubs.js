// Diagnostics and network stubs for the isolated battle page (this page only).
//   - console.error keeps stacks; ?trace=Module.method records the first throw with its stack
//   - SocketMgr / GameRoomSocket.send   -> logged, never sent (there is no socket anyway)
//   - PlayerModule.getMultiPlayerData   -> resolved at once (player data comes from StartGameP)
//   - BuildProxy.QuitRoomRequest        -> recorded, answered locally with the client's own result
(function () {
  "use strict";
  const SimBattle = (window.SimBattle = window.SimBattle || {});

  // Game code often catches and console.error()s; keep the stacks so the cause is visible.
  SimBattle.captureErrors = function ({ M, report, step }) {
    report.errors = [];
    const origError = console.error;
    console.error = function (...args) {
      const err = args.find((a) => a instanceof Error);
      if (report.errors.length < 20) {
        report.errors.push({
          msg: args.map((a) => (a instanceof Error ? String(a) : typeof a === "object" ? "[obj]" : String(a))).join(" ").slice(0, 300),
          stack: String((err || new Error()).stack).split("\n").slice(1, 8).map((l) => l.trim()).join(" | "),
          tick: report.tick,
        });
      }
      return origError.apply(this, args);
    };

    // Game code that catches and logs only String(err) loses the stack. ?trace=Module.method,...
    // wraps those methods so the first throw is recorded with its stack (diagnostics only).
    for (const spec of (new URLSearchParams(location.search).get("trace") || "").split(",").filter(Boolean)) {
      const [mod, meth] = spec.split(".");
      let proto;
      try { proto = M(mod).prototype; } catch (e) { step("trace: no such module", spec); continue; }
      const orig = proto[meth];
      if (typeof orig !== "function") { step("trace: no such method", spec); continue; }
      proto[meth] = function () {
        try { return orig.apply(this, arguments); } catch (e) {
          report.errors.push({ msg: `throw in ${spec}: ${e}`, stack: String(e && e.stack).split("\n").slice(1, 9).map((l) => l.trim()).join(" | "), tick: report.tick });
          throw e;
        }
      };
    }
  };

  SimBattle.stubNetwork = function ({ M, report, step, myPid }) {
    const net = (what, extra) => {
      report.netCalls.push({ what, extra });
      if (report.netCalls.length <= 50) console.warn("[sim] stubbed net call", what, extra || "");
    };
    for (const name of ["SocketMgr", "GameRoomSocket"]) {
      const sock = M(name).Ins;
      sock.send = function (module, cmd, c2s) {
        let cmdName = cmd;
        try { cmdName = this.getCmdName(module, cmd); } catch (e) { /* keep number */ }
        net(`${name}.send`, { module, cmd: cmdName });
      };
    }
    const PlayerModule = M("PlayerModule");
    PlayerModule.Ins.getMultiPlayerData = async () => { net("PlayerModule.getMultiPlayerData (resolved locally)"); };
    // Shape of PlayerModule.updatePlayerInfo's holder; only playerId is known (from StartGameP).
    PlayerModule.Ins._playerInfo = { info: { playerId: myPid }, playerMoney: undefined, compressionFightCap: 0, speedCardEndDt: 0 };
    step("player", { playerId: PlayerModule.Ins.playerId });
  };

  SimBattle.stubQuitRoom = function ({ M, report, step, rb, play, onQuit }) {
    M("BuildProxy").Ins.QuitRoomRequest = function (req, cbs) {
      report.quit = { type: req.type, extra: req.extra, endFrame: req.endFrame, totalTime: req.totalTime, battleType: req.battleType };
      // Play mode: keep the op log the game would upload, so a played battle can be replayed.
      if (play) report.quit.operations = rb.listItems(req.operations).map((o) => ({ operationType: o.operationType, playerId: o.playerId, operFrame: o.operFrame, index: o.index, args: o.args }));
      step("QuitRoom (local)", { type: req.type, endFrame: req.endFrame, totalTime: req.totalTime });
      const cb = cbs && cbs[0];
      if (cb) setTimeout(() => cb({ err: 0, result: req.type, clientReward: null, otherReward: null, extra: req.extra }), 0);
      onQuit();
    };
  };
})();

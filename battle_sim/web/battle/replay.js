// Op log replay and battle timing hooks. Captured ops are applied right before the engine's
// logicTick of their operFrame, exactly like the headless sim (lib/sim.js).
// ?play: no op log; the UI's own commits take the game's Local path and pauses are kept.
(function () {
  "use strict";
  const SimBattle = (window.SimBattle = window.SimBattle || {});

  SimBattle.installReplay = function ({ M, R, report, step, ops, play, myPid, start }) {
    const TDServer = M("TDServer").Ins;
    const TDServerProxy = M("TDServerProxy").Ins;
    const OperationInfo = R("TDServerDefine").OperationInfo;
    const Delegate = M("BattleEngineDelegate");
    let qi = 0;
    let replaying = false;
    const origHandle = TDServer.handleClientRequest;
    TDServer.handleClientRequest = function (op) {
      if (!replaying) report.foreignOps++;
      return origHandle.apply(this, arguments);
    };
    function applyNext(tick) {
      const op = ops[qi++];
      const o = new OperationInfo();
      Object.assign(o, { operationType: op.operationType, playerId: op.playerId, operFrame: op.operFrame, index: op.index, args: op.args });
      o.argsObj = op.args ? JSON.parse(op.args) : {};
      let r;
      replaying = true;
      try { TDServer.onCommitClientRequest(o); r = TDServer.handleClientRequest(o); } catch (e) { r = { success: false, error: String(e && e.stack || e) }; }
      replaying = false;
      report.applied++;
      if (!r || !r.success) report.failed.push({ tick, type: op.operationType, playerId: op.playerId, error: r && r.error && String(r.error).split("\n").slice(0, 6).map((l) => l.trim()).join(" | ") });
      return r;
    }
    // Ops the UI / director commit by themselves. The op log stays the only input: when the
    // committed op is the next logged one (same type + player, already due) the logged op is
    // applied in its place (e.g. the room-ready / start ops at frame 0 that gate the engine);
    // anything else is dropped and reported.
    if (!play) TDServerProxy.commitClientRequest = function (op) {
      const next = ops[qi];
      const tick = TDServer.curFrame;
      if (next && next.operationType === op.operationType && next.playerId === op.playerId && next.operFrame <= tick) {
        const r = applyNext(tick);
        report.viaUi = (report.viaUi || 0) + 1;
        return Promise.resolve(r && r.success);
      }
      report.dropped.push({ tick, type: op.operationType, playerId: op.playerId, args: op.argsObj });
      return Promise.resolve(false);
    };
    // ?speed=N: the battle's own speed control (BattleMainLoop.setTimeScale, what the in-game
    // speed button calls). Rendering only; at most one logic tick per frame (FrameSyncCocos).
    const speed = Number(new URLSearchParams(location.search).get("speed")) || 0;
    const MainLoop = M("BattleMainLoop");
    let mainLoop = null;
    const origBind = MainLoop.prototype.bind;
    MainLoop.prototype.bind = function () { mainLoop = this; return origBind.apply(this, arguments); };
    // The TD director pauses the battle while a blocking panel is open (wheel, summon choice,
    // ...; BattleTDBaseDirector.checkBlockTick) until the player acts. In a replay the log
    // already fixes when each op happened, and the real pause even started late (the panel
    // loads first: wheel opened at frame 1200, pick logged at 1220). So pauses are skipped
    // here and counted; the logic timeline is the op log's.
    const UIMgr = M("UIMgr").Ins;
    const WHEEL_VIEW = "TDRouletteWheel";
    const OP_SELECT_ELITE = R("BuildProto").EClientOperationType_Build_Enum.SelectElite;
    // Play mode keeps the real pause (the player has to answer the panel); only counted.
    report.pausesSkipped = {};
    const Director = M("BattleTDBaseDirector");
    const origPause = Director.prototype.pause;
    Director.prototype.pause = function () {
      const why = this._blockViewName || "?";
      report.pausesSkipped[why] = (report.pausesSkipped[why] || 0) + 1;
      if (play) return origPause.apply(this, arguments);
    };
    const origTick = Delegate.prototype.logicTick;
    Delegate.prototype.logicTick = function () {
      if (TDServer._delegate === this) {
        const tick = this.currentTick;
        report.tick = tick;
        if (speed && mainLoop && tick === 1) { mainLoop.setTimeScale(speed); step("speed", { timeScale: speed }); }
        while (qi < ops.length && ops[qi].operFrame <= tick) {
          const next = ops[qi];
          // The player's wheel pick (SelectElite) comes from the wheel panel as it closes.
          // Close it now so the UI follows the log; the logged op is applied below, and the
          // panel's own late commit (close is animated, ~3 ticks later) is dropped.
          if (next.operationType === OP_SELECT_ELITE && next.playerId === myPid && UIMgr.isOpen(WHEEL_VIEW)) {
            UIMgr.close(WHEEL_VIEW);
            report.wheelClosed = (report.wheelClosed || 0) + 1;
            if (ops[qi] !== next) continue; // already applied through the panel's commit
          }
          applyNext(tick);
        }
        const el = document.getElementById("simStatus");
        if (el && tick % 50 === 0) el.textContent = play
          ? `play ${start.uuid} L${start.level}  tick ${tick}  ops ${TDServerProxy._clientOperationRecord.length}`
          : `battle ${start.uuid} L${start.level}  tick ${tick}  ops ${qi}/${ops.length}`;
      }
      return origTick.apply(this, arguments);
    };
  };

  // Game's QuitRoom (captured) vs the one this page produced.
  SimBattle.compareQuit = function (game, mine) {
    if (!mine) return { ok: false, lines: ["no QuitRoom produced"] };
    const a = JSON.parse(game.extra || "{}"), b = JSON.parse(mine.extra || "{}");
    const lines = [];
    let ok = true;
    const endOk = game.endFrame ? game.endFrame === mine.endFrame : game.totalTime === mine.totalTime;
    ok = ok && endOk;
    lines.push(`${endOk ? "OK  " : "DIFF"} end: game endFrame ${game.endFrame} totalTime ${game.totalTime}, page endFrame ${mine.endFrame} totalTime ${mine.totalTime}`);
    for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) {
      if (k === "fightCap") continue;
      const x = JSON.stringify(a[k]), y = JSON.stringify(b[k]);
      ok = ok && x === y;
      lines.push(`${x === y ? "OK  " : "DIFF"} ${k}: game=${(x || "").slice(0, 120)}${x === y ? "" : "  page=" + (y || "").slice(0, 120)}`);
    }
    return { ok, lines };
  };
})();

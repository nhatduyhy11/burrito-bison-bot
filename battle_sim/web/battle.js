// Open a captured battle in the isolated page and replay its op log with the game's own
// battle view. Loaded by boot.js when the URL has ?battle=<uuid>; runs after boot.
//
// Entry point is the same one the room socket uses: TDModule.onStartGamePPush(StartGameP).
// Everything that would reach a server is stubbed here, in this page only:
//   - PlayerModule.getMultiPlayerData   -> resolved at once (player data comes from StartGameP)
//   - TDServerProxy.commitClientRequest -> dropped and logged (the op log is the only input)
//   - BuildProxy.QuitRoomRequest        -> recorded, answered locally with the client's own result
//   - SocketMgr / GameRoomSocket.send   -> logged, never sent (there is no socket anyway)
// Captured ops are applied right before the engine's logicTick of their operFrame, exactly
// like the headless sim (lib/sim.js).
// ?play: no op log. The player uses the battle UI; the commit / pause stubs above are not
// installed, so ops take the game's own Local path. ?seed=random|<uuid> changes the RNG seed.
(function () {
  "use strict";

  const DESIGN = { width: 720, height: 1280 }; // UIMgr.init defaults (Main passes the launch scene's)

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
    const s2c = rb.build("StartGameP_BuildRoom_S2C", start);
    const ops = play ? [] : rb.listItems(quit.operations).slice().sort((a, b) => a.operFrame - b.operFrame || a.index - b.index);
    const myPid = rb.listItems(start.playerInfos)[0].playerId;
    if (play) window.__simPlayedStart = start; // sandbox.py saves it with the QuitRoom (not polled: ~24KB)
    const report = (sim.battle = {
      mode: play ? "play" : "replay", uuid: start.uuid, capturedUuid: sim.capture.start.uuid, myPid,
      ops: ops.length, applied: 0, failed: [], dropped: [], foreignOps: 0, netCalls: [], tick: 0, quit: null,
    });
    const net = (what, extra) => {
      report.netCalls.push({ what, extra });
      if (report.netCalls.length <= 50) console.warn("[sim] stubbed net call", what, extra || "");
    };

    // Game code often catches and console.error()s; keep the stacks so the cause is visible.
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

    // --- Main-like setup: only what the battle needs (no login, SDK, lobby modules) ---
    cc.view.setDesignResolutionSize(DESIGN.width, DESIGN.height, cc.ResolutionPolicy.FIXED_WIDTH);
    const canvas = cc.director.getScene().getChildByName("Canvas");
    const canvasWidget = canvas.getComponent(cc.Widget); // boot.js: Canvas stretched to the screen
    if (canvasWidget) canvasWidget.updateAlignment();
    fixMainCamera(canvas);
    const viewRoot = new cc.Node("ViewRoot");
    canvas.addChild(viewRoot);
    M("NodeUtils").addWidget(viewRoot, 0, 0, 0, 0).updateAlignment();
    R("ResourceManager").resource.ResourceManager.sInstance.init(30, 5, 0);
    M("UIMgr").Ins.init(viewRoot, M("ResPathUtils").ViewPrefabPath, DESIGN.width, viewRoot.height, 60);
    const battleRoot = new cc.Node("BattleRoot");
    canvas.addChild(battleRoot);
    M("BattleMgr").Ins.init(battleRoot);
    M("BattleModule").Ins._loadCacheData();
    // Main.update / lateUpdate drive the game's timers and managers every frame.
    const Driver = cc.Class({
      name: "SimMainDriver", extends: cc.Component,
      update(dt) { M("UpdateMgr").Ins.onUpdate(dt); M("GameMgr").Ins.onUpdate(dt); },
      lateUpdate(dt) { M("UpdateMgr").Ins.onLateUpdate(dt); },
    });
    canvas.addComponent(Driver);
    step("main setup", { design: DESIGN, frame: cc.view.getFrameSize() });

    // --- Network stubs (this page only) ---
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

    // Main.initModule: ModuleMgr.init (onLoad) + enterGame (onEnterGame) for every module, as
    // after login, so module state the battle UI reads (config maps, listeners) exists. Same
    // order as ModuleMgr.init, but each call is isolated: a lobby module failing for lack of
    // login data is recorded and the rest still run. Their requests hit the socket stubs above.
    const mm = M("ModuleMgr").Ins;
    for (const cls of mm.modules) mm._store.push(cls.Ins);
    mm.modules.length = 0;
    mm._store.sort((e, t) => (t.initPriority != e.initPriority ? t.initPriority - e.initPriority : t.moduleName - e.moduleName));
    report.moduleErrors = [];
    for (const phase of ["onLoad", "onEnterGame"]) {
      for (let i = 0; i < mm._store.length; i++) {
        const mod = mm._store.get(i);
        try { mod[phase](); } catch (e) {
          report.moduleErrors.push({ phase, module: cc.js.getClassName(mod) || (mod.constructor && mod.constructor.name), error: String(e).slice(0, 200) });
        }
      }
    }
    step("modules", { count: mm._store.length, failed: report.moduleErrors.length });

    const TDServer = M("TDServer").Ins;
    const TDServerProxy = M("TDServerProxy").Ins;
    const BuildProxy = M("BuildProxy").Ins;
    BuildProxy.QuitRoomRequest = function (req, cbs) {
      report.quit = { type: req.type, extra: req.extra, endFrame: req.endFrame, totalTime: req.totalTime, battleType: req.battleType };
      // Play mode: keep the op log the game would upload, so a played battle can be replayed.
      if (play) report.quit.operations = rb.listItems(req.operations).map((o) => ({ operationType: o.operationType, playerId: o.playerId, operFrame: o.operFrame, index: o.index, args: o.args }));
      step("QuitRoom (local)", { type: req.type, endFrame: req.endFrame, totalTime: req.totalTime });
      const cb = cbs && cbs[0];
      if (cb) setTimeout(() => cb({ err: 0, result: req.type, clientReward: null, otherReward: null, extra: req.extra }), 0);
      finish();
    };

    // --- Op log replay: before each logicTick, apply the ops due at that tick ---
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

    // Normally set by TDModule / HangUpModule.onEnterGame above. Fallbacks (same values the
    // game uses) only if those modules failed, so the battle can still open.
    const TDModule = M("TDModule").Ins;
    if (!TDModule.RoBotWaitTimeAndMoveSpeed) {
      TDModule.RoBotWaitTimeAndMoveSpeed = JSON.parse(M("ConstLO").get("RoBotWaitTimeAndMoveSpeed").constValue);
      step("fallback: RoBotWaitTimeAndMoveSpeed");
    }
    const BattleModule = M("BattleModule").Ins;
    const BattleMgr = M("BattleMgr").Ins;
    if (!BattleModule.getConfig(start.battleType)) {
      // Campaign registration as HangUpModule.onEnterGame / _battleRecived do it.
      const cfg = new (M("BattleModuleConfig"))();
      cfg.framePrefab = "battle_frame_td";
      cfg.frameClass = "BattleAdvFrame";
      cfg.customShellView = "BattleTDAdvView";
      cfg.isFullView = true;
      cfg.customResultView = "BattleResultViewAdventure";
      cfg.onOpenResultView = () => R("BattleClientDef").AbortType.DEFAULT;
      BattleModule.setConfig(start.battleType, cfg);
      BattleMgr.addListener(start.battleType, (_e, args) => {
        const vo = BattleModule.getBattleByUUID(args[0]);
        if (!vo) return;
        vo.inject(M("BattleTDAdvDirector"));
        BattleMgr.startBattle(start.battleType);
      }, report); // Listener ignores handlers without a target
      step("fallback: battle config", { battleType: start.battleType });
    }

    // --- Enter the battle exactly like the room socket's StartGameP push ---
    let done = false;
    function finish() {
      if (done) return;
      done = true;
      const st = TDServer._delegate && TDServer._delegate._battleStatistics;
      report.result = st && { result: st.result, resultReason: st.resultReason };
      if (play) {
        step("battle end", { tick: report.tick, ops: report.quit.operations.length, extra: report.quit.extra && JSON.parse(report.quit.extra) });
      } else {
        report.compare = compare(quit, report.quit);
        step("battle end", { tick: report.tick, applied: report.applied, failed: report.failed.length, dropped: report.dropped.length, match: report.compare.ok });
      }
      sim.state = "done";
    }
    await M("TDModule").Ins.onStartGamePPush(s2c);
    step("StartGameP pushed", { uuid: start.uuid, level: start.level, battleType: start.battleType });
  };

  // cc.Canvas's "Main Camera" renders every group and clears color. The battle prefab has its
  // own camera_battle (groups battle_ground*, depth -10) that renders first, so the Main Camera
  // wiped it and redrew the map without the battle camera offset (wrong area, no units).
  // The game's launch scene sets this up in the editor; here: Main Camera = UI only, no color
  // clear, and a lowest-depth camera that only clears the frame.
  function fixMainCamera(canvas) {
    const main = canvas.getComponentInChildren(cc.Camera);
    if (!main) return;
    const groups = cc.game.groupList || [];
    for (const g of ["battle_ground", "battle_ground_bg"]) {
      const i = groups.indexOf(g);
      if (i >= 0) main.cullingMask &= ~(1 << i);
    }
    main.clearFlags = cc.Camera.ClearFlags.DEPTH | cc.Camera.ClearFlags.STENCIL;
    const node = new cc.Node("ClearCamera");
    const clear = node.addComponent(cc.Camera);
    clear.cullingMask = 0;
    clear.depth = -100;
    clear.backgroundColor = cc.Color.BLACK;
    clear.clearFlags = cc.Camera.ClearFlags.COLOR | cc.Camera.ClearFlags.DEPTH | cc.Camera.ClearFlags.STENCIL;
    canvas.addChild(node);
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

  // Game's QuitRoom (captured) vs the one this page produced.
  function compare(game, mine) {
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
  }
})();

"use strict";
// Headless battle: game's own TDServer + BattleEngineDelegate driven tick by tick.
const fs = require("fs");
const path = require("path");
const { loadBundle } = require("./bundle_loader");
const { loadConfig } = require("./config_loader");
const { makeRebuilder } = require("./proto_rebuild");

function readJson(p) { return JSON.parse(fs.readFileSync(p, "utf8")); }

class Sim {
  constructor({ bundle, config, preloadConfig, mapsDir, log = () => {} }) {
    this.log = log;
    const captured = [];
    this.gameLog = captured;
    const quietConsole = {
      log: (...a) => captured.push(["log", a]), warn: (...a) => captured.push(["warn", a]),
      error: (...a) => captured.push(["error", a]), info() {}, debug() {}, trace() {},
      group() {}, groupCollapsed() {}, groupEnd() {}, time() {}, timeEnd() {},
    };
    const { require: req, ctx } = loadBundle(bundle, { console: quietConsole });
    this.req = req;
    this.ctx = ctx;
    if (preloadConfig) loadConfig(req, preloadConfig, "PreloadConfigParser");
    loadConfig(req, config);
    this.mapsDir = mapsDir;
    this.rb = makeRebuilder(req);
  }

  // Load a battle from captured StartGameP JSON.
  setup(startGamePJson, hooks = {}) {
    const req = this.req;
    const s2c = this.rb.build("StartGameP_BuildRoom_S2C", startGamePJson);
    this.s2c = s2c;
    const TDServer = req("TDServer").TDServer.Ins;
    this.td = TDServer;
    const { BattleEngineDelegate, EDebugLevel } = req("BattleEngineDelegate");
    const delegate = new BattleEngineDelegate();
    this.delegate = delegate;

    // TDServer ("local server") state for this battle: rand seed, room, lottery cfgs.
    TDServer.onStartGamePPush(s2c);

    // Fake main loop: the delegate calls back into it (onUnitCreate, ...).
    const events = (this.events = []);
    const mainLoop = new Proxy({}, {
      get: (_t, k) => (...args) => {
        if (hooks.onMainLoop) hooks.onMainLoop(String(k), args);
        events.push([String(k), delegate._battleEngine ? delegate.currentTick : -1]);
      },
    });
    delegate.bindEngine(mainLoop, EDebugLevel.Release);

    const bgId = req("BattleRoomHelper").BattleRoomHelper.Ins.getProvider(s2c.battleType).GetBattleGroundId(s2c.level);
    const bg = req("BattleGroundLO").BattleGroundLO.get(bgId);
    const mapJson = readJson(path.join(this.mapsDir, bg.tiledBg + ".json"));
    const brushName = (mapJson.tilesets.find((t) => /brush/.test(t.source)) || {}).source;
    const brushJson = readJson(path.join(this.mapsDir, path.basename(brushName, ".json") + ".json"));
    const commonJson = readJson(path.join(this.mapsDir, "common.json"));
    delegate.initMapData(mapJson, commonJson, brushJson, bg);
    TDServer.bind(delegate);
    this.bg = bg;
    return { bgId, tiledBg: bg.tiledBg };
  }

  async start() {
    const d = this.delegate;
    await d.preStart(this.s2c);
    if (typeof d.initModuleConfig === "function" && !d.moduleConfig) d.initModuleConfig();
    d.start();
  }

  // Apply one captured client operation through the local server.
  applyOp(op) {
    const req = this.req;
    const OperationInfo = req("TDServerDefine").OperationInfo;
    const o = new OperationInfo();
    o.operationType = op.operationType;
    o.playerId = op.playerId;
    o.operFrame = op.operFrame;
    o.index = op.index;
    o.args = op.args;
    o.argsObj = op.args ? JSON.parse(op.args) : {};
    this.td.onCommitClientRequest(o);
    return this.td.handleClientRequest(o);
  }

  get tick() { return this.delegate.currentTick; }

  // Replay ops (sorted by operFrame, index) until the battle ends or maxTick.
  run(ops, { maxTick = 30000, onTick } = {}) {
    const d = this.delegate;
    const queue = ops.slice().sort((a, b) => a.operFrame - b.operFrame || a.index - b.index);
    let qi = 0;
    const applied = [];
    while (d.currentTick < maxTick) {
      while (qi < queue.length && queue[qi].operFrame <= d.currentTick) {
        const op = queue[qi++];
        let r;
        try { r = this.applyOp(op); } catch (e) { r = { success: false, error: String(e && e.stack || e) }; }
        applied.push({ tick: d.currentTick, op, r: r && { success: r.success, error: r.error } });
      }
      const result = d._battleStatistics && d._battleStatistics.result;
      if (result) break;
      d.logicTick();
      if (onTick) onTick(this);
    }
    return { applied, remaining: queue.slice(qi) };
  }
}

module.exports = { Sim };

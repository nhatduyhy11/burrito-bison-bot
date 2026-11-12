// Main-like setup: only what the battle needs (no login, SDK, lobby modules).
(function () {
  "use strict";
  const SimBattle = (window.SimBattle = window.SimBattle || {});

  const DESIGN = { width: 720, height: 1280 }; // UIMgr.init defaults (Main passes the launch scene's)

  SimBattle.setupMain = function ({ M, R, step }) {
    // Main.setDesignResolutionSize: frames wider than 9:16 (desktop windows) use FIXED_HEIGHT
    // with a 30px status bar, and Main opens BackGroundView to cover the sides.
    const frame = cc.view.getFrameSize();
    const sideCover = frame.width / frame.height > DESIGN.width / DESIGN.height;
    if (!sideCover) {
      cc.view.setDesignResolutionSize(DESIGN.width, DESIGN.height, cc.ResolutionPolicy.FIXED_WIDTH);
    } else {
      M("DeviceUtils").Ins.statusBarHeight = 30;
      cc.view.setDesignResolutionSize(DESIGN.width, DESIGN.height, cc.ResolutionPolicy.FIXED_HEIGHT);
    }
    const canvas = cc.director.getScene().getChildByName("Canvas");
    const canvasWidget = canvas.getComponent(cc.Widget); // boot.js: Canvas stretched to the screen
    if (canvasWidget) canvasWidget.updateAlignment();
    fixMainCamera(canvas);
    const viewRoot = new cc.Node("ViewRoot");
    canvas.addChild(viewRoot);
    M("NodeUtils").addWidget(viewRoot, 0, 0, 0, 0).updateAlignment();
    R("ResourceManager").resource.ResourceManager.sInstance.init(30, 5, 0);
    M("UIMgr").Ins.init(viewRoot, M("ResPathUtils").ViewPrefabPath, DESIGN.width, viewRoot.height, 60);
    if (sideCover) M("UIMgr").Ins.open(M("BackGroundView"), M("UILayerType").SideCover);
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
  };

  // Main.initModule: ModuleMgr.init (onLoad) + enterGame (onEnterGame) for every module, as
  // after login, so module state the battle UI reads (config maps, listeners) exists. Same
  // order as ModuleMgr.init, but each call is isolated: a lobby module failing for lack of
  // login data is recorded and the rest still run. Their requests hit the network stubs.
  SimBattle.initModules = function ({ M, report, step }) {
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
  };

  // Normally set by TDModule / HangUpModule.onEnterGame. Fallbacks (same values the game
  // uses) only if those modules failed, so the battle can still open.
  const BATTLE_CONFIGS = {
    3: { // EBattleTypeHangUpSystem
      cfg: { frameClass: "BattleAdvFrame", customShellView: "BattleTDAdvView", isFullView: true, customResultView: "BattleResultViewAdventure" },
      director: "BattleTDAdvDirector",
    },
    21: { // EBattleTypeGuildNavalWar (U Đô)
      cfg: { frameClass: "TDGuildPVPBattleFram", customShellView: "BattleTDGuildPVPView", customResultView: "BattleResultViewGuildPVP" },
      director: "BattleTDGuildPVPDirector",
    },
  };

  SimBattle.ensureBattleConfig = function ({ M, R, report, step, battleType }) {
    const TDModule = M("TDModule").Ins;
    if (!TDModule.RoBotWaitTimeAndMoveSpeed) {
      TDModule.RoBotWaitTimeAndMoveSpeed = JSON.parse(M("ConstLO").get("RoBotWaitTimeAndMoveSpeed").constValue);
      step("fallback: RoBotWaitTimeAndMoveSpeed");
    }
    const BattleModule = M("BattleModule").Ins;
    const BattleMgr = M("BattleMgr").Ins;
    if (!BattleModule.getConfig(battleType)) {
      // Registration as the owning module does it: HangUpModule (campaign), GuildPVPModule (capital).
      const known = BATTLE_CONFIGS[battleType] || BATTLE_CONFIGS[3];
      const cfg = new (M("BattleModuleConfig"))();
      cfg.framePrefab = "battle_frame_td";
      Object.assign(cfg, known.cfg);
      cfg.onOpenResultView = () => R("BattleClientDef").AbortType.DEFAULT;
      BattleModule.setConfig(battleType, cfg);
      BattleMgr.addListener(battleType, (_e, args) => {
        const vo = BattleModule.getBattleByUUID(args[0]);
        if (!vo) return;
        vo.inject(M(known.director));
        BattleMgr.startBattle(battleType);
      }, report); // Listener ignores handlers without a target
      step("fallback: battle config", { battleType });
    }
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
})();

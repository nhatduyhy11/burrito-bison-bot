// Isolated boot of the game's own engine + code bundle from the local mirror.
// Mirrors window.boot() (main.<h>.js) up to cc.game.run, but runs an empty scene
// instead of the launch scene, so Main / LoginMgr (login, SDK, servers) never start.
// Progress and results land in window.__sim (read by sandbox.py).
(function () {
  "use strict";
  const sim = (window.__sim = { state: "booting", steps: [], checks: {}, error: null });
  const statusEl = () => document.getElementById("simStatus");
  function step(name, extra) {
    sim.steps.push({ t: Math.round(performance.now()), name, extra });
    const el = statusEl();
    if (el) el.textContent = sim.steps.slice(-12).map((s) => `${(s.t / 1000).toFixed(1)}s ${s.name}${s.extra ? " " + JSON.stringify(s.extra) : ""}`).join("\n");
    console.log("[sim]", name, extra || "");
  }
  function fail(where, e) {
    sim.state = "error";
    sim.error = { where, message: String((e && e.message) || e), stack: e && e.stack ? String(e.stack).split("\n").slice(0, 8).join("\n") : null };
    step("ERROR " + where, sim.error.message);
  }
  const loadScript = (src) => new Promise((ok, ko) => {
    const s = document.createElement("script");
    s.src = src; s.async = false;
    s.onload = () => ok(); s.onerror = () => ko(new Error("script failed: " + src));
    document.head.appendChild(s);
  });
  const getJson = async (url) => { const r = await fetch(url); if (!r.ok) throw new Error(`HTTP ${r.status} ${url}`); return r.json(); };
  const getBytes = async (url) => { const r = await fetch(url); if (!r.ok) throw new Error(`HTTP ${r.status} ${url}`); return new Uint8Array(await r.arrayBuffer()); };
  const cb2p = (fn) => new Promise((ok, ko) => fn((err, v) => (err ? ko(err) : ok(v))));
  const R = (name) => window.__require(name);

  // Same global patch the game installs in Main.doHook (lenient JSON.parse).
  function patchJsonParse() {
    if (JSON._parse == null) {
      JSON._parse = JSON.parse;
      JSON.parse = function (e, t) {
        return typeof e === "object" || Array.isArray(e) ? e : e == null ? [] : e === "" ? [] : JSON._parse((e.trim && e.trim()) || e, t);
      };
    }
  }

  function loadConfigBin(bytes, parserName) {
    const QuickLZ = R("QuickLZ").QuickLZ;
    const BinaryReader = R("BinaryReader").BinaryReader;
    const Parser = R(parserName)[parserName];
    const data = QuickLZ.decompress(bytes);
    const reader = new BinaryReader();
    reader.init(data);
    new Parser().writeBinaryDataWhenRead(reader);
    return data.length;
  }

  async function main() {
    const params = new URLSearchParams(location.search);
    const deploy = await getJson("/__sim/deploy.json");
    step("deploy", { clientVer: deploy.clientVer, main: deploy.bundleVers.main });

    // Engine + settings, from the deploy's own manifest (main.<h>.js is replaced by this file).
    await loadScript(`/manifest.${deploy.clientVer}.js`);
    const engine = window.manifest.initial.find((f) => /^cocos2d-js-min\./.test(f));
    await loadScript("/" + engine);
    await loadScript("/" + deploy.settingsFile);
    const settings = window._CCSettings;
    step("engine", { engine, cc: cc.ENGINE_VERSION });

    patchJsonParse();
    cc.assetManager.init({ bundleVers: settings.bundleVers, remoteBundles: settings.remoteBundles, server: settings.server });
    for (const js of settings.jsList) await loadScript("/src/" + js);
    step("jsList", settings.jsList.length);

    // Same bundle order as boot(): internal + login, then main (game code).
    await Promise.all(["internal", "login"].map((b) => cb2p((cb) => cc.assetManager.loadBundle(b, cb))));
    await cb2p((cb) => cc.assetManager.loadBundle("main", cb));
    step("main bundle", { modules: typeof window.__require === "function" });

    // Start the engine with an empty scene instead of settings.launchScene.
    await new Promise((ok) => cc.game.run({
      id: "GameCanvas", debugMode: cc.debug.DebugMode.ERROR, showFPS: false, frameRate: 60,
      groupList: settings.groupList, collisionMatrix: settings.collisionMatrix,
    }, ok));
    const scene = new cc.Scene();
    const canvasNode = new cc.Node("Canvas");
    canvasNode.addComponent(cc.Canvas);
    scene.addChild(canvasNode);
    cc.director.runSceneImmediate(scene);
    step("engine running", { frame: cc.view.getFrameSize() });

    // Remote config, from the local cache (same parsers the game uses after login).
    const configs = await getJson("/__sim/configs.json");
    const configVer = params.get("config") || configs[0];
    if (!configVer) throw new Error("no cached config; replay a battle or run versions.ensureConfig first");
    const pre = loadConfigBin(await getBytes(`/__sim_config/${configVer}/preload_config.bin`), "PreloadConfigParser");
    const cfg = loadConfigBin(await getBytes(`/__sim_config/${configVer}/config.bin`), "ConfigParser");
    const CP = R("ConfigParser").ConfigParser;
    sim.checks.config = { requested: configVer, loaded: `${CP.branch}_${CP.version}`, preloadBytes: pre, configBytes: cfg };
    step("config", sim.checks.config);

    // Battle-side bundles.
    const bundles = ["resources", "battle", "battleConfig", "battleSkillRes", "towerDefense", "organ"];
    for (const b of bundles) await cb2p((cb) => cc.assetManager.loadBundle(b, cb));
    sim.checks.bundles = bundles.filter((b) => cc.assetManager.getBundle(b));
    step("bundles", sim.checks.bundles);

    // Sanity: config tables answer, and a battle asset loads through the engine.
    const bg = R("BattleGroundLO").BattleGroundLO.get(10051);
    sim.checks.tables = { battleGround10051: bg && bg.tiledBg, heroCount: countLO("HeroLO") };
    step("tables", sim.checks.tables);
    const battle = cc.assetManager.getBundle("battle");
    const mapPath = `prefabs/tiledBg/map/${bg.tiledBg}`;
    const prefab = await cb2p((cb) => battle.load(mapPath, cc.Prefab, cb));
    sim.checks.mapPrefab = { path: mapPath, name: prefab && prefab.name };
    step("map prefab", sim.checks.mapPrefab);

    // ext-res (spine models etc.) through the game's own loader, as Main.onLoad sets it up on web.
    // init() fetches ext-res/version_<ver>.json (logical -> hashed path) and resolves when done.
    const verOk = await window.aswallow.extAssetMgr.init(null, null, `version_${deploy.clientVer}.json`, 5);
    if (!verOk) throw new Error("ext-res version manifest failed to load");
    const modelUrl = params.get("model") || "model/Boss_014/Boss_014.json";
    const model = await cb2p((cb) => window.aswallow.extAssetMgr.load({ url: modelUrl }, cb));
    sim.checks.extRes = { url: modelUrl, type: model && model.constructor && cc.js.getClassName(model) };
    step("ext-res", sim.checks.extRes);

    sim.state = "ready";
    step("READY");
  }

  function countLO(name) {
    try {
      const LO = R(name)[name];
      if (typeof LO.tryToInit === "function") LO.tryToInit();
      const store = LO.store; // game List of rows
      return store ? (typeof store.length === "number" ? store.length : Object.keys(store).length) : null;
    } catch (e) { return String(e.message || e); }
  }

  window.addEventListener("error", (e) => { if (sim.state !== "error") step("window.error", String(e.message)); });
  window.addEventListener("unhandledrejection", (e) => step("unhandledrejection", String(e.reason && e.reason.message || e.reason)));
  main().catch((e) => fail("main", e));
})();

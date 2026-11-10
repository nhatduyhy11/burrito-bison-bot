"use strict";
// Minimal Cocos/browser globals so the battle-logic closure of the bundle can run
// in Node. Only what the TDServer/BattleEngineDelegate closure touches; anything
// else is a permissive no-op proxy so failures surface as missing behaviour, not
// as load-time crashes. Logging is collected, not printed.

function noopProxy(name) {
  const fn = function () { return noopProxy(name + "()"); };
  return new Proxy(fn, {
    get(_t, k) {
      if (k === Symbol.toPrimitive) return () => "";
      if (k === "then") return undefined;
      return noopProxy(name + "." + String(k));
    },
    apply() { return noopProxy(name + "()"); },
    construct() { return noopProxy("new " + name); },
  });
}

function installStubs(ctx, opts = {}) {
  const g = ctx;
  g.window = g;
  g.self = g;
  g.globalThis = g;
  g.console = opts.console || console;
  g.setTimeout = setTimeout;
  g.clearTimeout = clearTimeout;
  g.setInterval = setInterval;
  g.clearInterval = clearInterval;
  g.Promise = Promise;
  g.TextDecoder = TextDecoder;
  g.TextEncoder = TextEncoder;
  g.performance = { now: () => Number(process.hrtime.bigint() / 1000000n) };
  g.navigator = { userAgent: "node", language: "en" };
  g.document = noopProxy("document");
  g.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };

  // i18n is used both as i18n("x") and as a tagged template i18n(strings, ...args).
  g.i18n = function (s, ...args) {
    if (Array.isArray(s)) return s.reduce((acc, part, i) => acc + part + (i < args.length ? args[i] : ""), "");
    return s;
  };

  const easing = {};
  ["sine", "quad", "cubic", "quart", "quint", "expo", "circ", "elastic", "back", "bounce"].forEach((n) => {
    ["In", "Out", "InOut"].forEach((s) => { easing[n + s] = (t) => t; });
  });

  const classByName = {};
  const js = {
    mixin(target, ...srcs) { srcs.forEach((s) => s && Object.assign(target, s)); return target; },
    setClassName(name, ctor) { classByName[name] = ctor; if (ctor) ctor.__classname__ = name; },
    getClassByName(name) { return classByName[name]; },
    getClassName(obj) {
      if (!obj) return "";
      const c = typeof obj === "function" ? obj : obj.constructor;
      return (c && (c.__classname__ || c.name)) || "";
    },
  };

  // Decorators used by components: @ccclass, @property(...) etc. -> identity.
  const decorator = (target) => target;
  const decoFactory = function (a) {
    if (typeof a === "function") return a; // @ccclass without args
    return decorator;
  };
  const property = function (a, b, c) {
    if (a && typeof a === "object" && typeof b === "string") return c; // @property used bare
    return function (_t, _k, d) { return d; };
  };

  class Component {}
  class Node {}
  class Vec2 { constructor(x = 0, y = 0) { this.x = x; this.y = y; } }
  class Vec3 { constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; } }

  g.cc = {
    _RF: (() => {
      const stack = [];
      return {
        push(module, uuid, script) { stack.push({ module, uuid, script }); },
        pop() { stack.pop(); },
        peek() { return stack[stack.length - 1] || { script: "" }; },
      };
    })(),
    _decorator: {
      ccclass: decoFactory, property, menu: decoFactory, executeInEditMode: decorator,
      requireComponent: () => decorator, disallowMultiple: decorator, executionOrder: () => decorator,
      inspector: () => decorator, playOnFocus: decorator, help: () => decorator,
    },
    js,
    easing,
    v2: (x, y) => new Vec2(x, y),
    v3: (x, y, z) => new Vec3(x, y, z),
    v: (x, y) => new Vec2(x, y),
    Vec2, Vec3, Component, Node,
    sys: { isBrowser: false, isNative: false, platform: "node", os: "node" },
    game: { getFrameRate: () => 60, on() {}, off() {} },
    director: { getScheduler: () => ({ schedule() {}, unschedule() {} }), getScene: () => null },
    tween: () => noopProxy("cc.tween()"),
    Texture2D: class {}, AudioClip: class {}, Asset: class {}, JsonAsset: class {},
    assetManager: { assets: new Map(), releaseUnusedAssets() {} },
    AssetManager: { Cache: class { constructor() { this._map = new Map(); } } },
    log() {}, warn() {}, error() {},
    Enum: (o) => o,
    Class: (def) => {
      const ctor = (def && def.ctor) || function () {};
      if (def && def.extends) Object.setPrototypeOf(ctor.prototype, def.extends.prototype);
      if (def && def.properties) Object.assign(ctor.prototype, def.properties);
      return ctor;
    },
  };
  return g;
}

module.exports = { installStubs, noopProxy };

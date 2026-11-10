"use strict";
// Load the game's browserify bundle (assets/main/index.<hash>.js) into a Node vm
// context WITHOUT running its entry modules. Returns a require(name) that lazily
// evaluates only the modules actually asked for (and their deps).
const fs = require("fs");
const vm = require("vm");
const { installStubs } = require("./stubs");

const LOADER_RE = /^window\.__require=function e\(t,o,i\)\{[\s\S]{0,2000}?return n\}\(/;

function loadBundle(bundlePath, opts = {}) {
  const source = fs.readFileSync(bundlePath, "utf8");
  const m = LOADER_RE.exec(source);
  if (!m) throw new Error("bundle loader prefix not recognised: " + bundlePath);

  const ctx = vm.createContext({});
  installStubs(ctx, opts);
  // Same global patch the game installs in Main.onLoad: lenient JSON.parse
  // ("" / null -> [], objects passed through). Battle code relies on it.
  vm.runInContext(
    'null==JSON._parse&&(JSON._parse=JSON.parse,JSON.parse=function(e,t){return"object"==typeof e||Array.isArray(e)?e:null==e?[]:""==e?[]:JSON._parse(e.trim&&e.trim()||e,t)});',
    ctx
  );
  ctx.__bundleCapture = (table) => { ctx.__bundleTable = table; return function () {}; };
  vm.runInContext("__bundleCapture(" + source.slice(m[0].length), ctx, {
    filename: bundlePath,
  });
  const table = ctx.__bundleTable;
  if (!table) throw new Error("capture stub was not called");

  const cache = Object.create(null);
  function req(key) {
    if (cache[key]) return cache[key].exports;
    const entry = table[key];
    if (!entry) throw new Error("module not found: " + key);
    const [fn, deps] = entry;
    const module = { exports: {} };
    cache[key] = module;
    const localRequire = (p) => {
      const k = deps && Object.prototype.hasOwnProperty.call(deps, p) ? deps[p] : p;
      return req(k);
    };
    try {
      fn.call(module.exports, localRequire, module, module.exports);
    } catch (e) {
      delete cache[key]; // don't leave a half-initialised module behind
      if (!e.__bundlePath) { e.__bundlePath = [key]; } else e.__bundlePath.push(key);
      throw e;
    }
    return module.exports;
  }
  ctx.__require = req;
  ctx.window.__require = req;
  return { require: req, ctx, table };
}

module.exports = { loadBundle };

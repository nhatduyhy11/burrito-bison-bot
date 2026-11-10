"use strict";
// Rebuild real proto message instances (with the game's List / Dictionary types)
// from the JSON produced by the research hook, using the game's own *_Def schemas.
//
// Hook JSON shapes:
//   List       -> {"0": v, "1": v, ..., "_length": n, "_TempSort": [], ...}
//   Dictionary -> {"_keyList": <List>, "_valueList": <List>, "_keyToIndex": {...}, ...}

function makeRebuilder(req) {
  const List = req("List").List;
  const Dictionary = req("Dictionary").Dictionary;
  const PF = req("PFType").PFType;
  const ctorName = new Map(); // constructor -> "Name_NS_S2C"
  const loadedNs = new Set();

  function nsOf(name) {
    const parts = name.split("_");
    return parts[parts.length - 2];
  }
  function loadNs(ns) {
    if (loadedNs.has(ns)) return;
    loadedNs.add(ns);
    const proto = req(ns + "Proto");
    for (const k of Object.keys(proto)) {
      if (typeof proto[k] === "function") ctorName.set(proto[k], k);
    }
  }
  function classOf(name) {
    const ns = nsOf(name);
    loadNs(ns);
    return req(ns + "Proto")[name];
  }
  function defOf(name) {
    const ns = nsOf(name);
    const holder = req(ns + "Define")[ns + "Define"];
    const fn = holder && holder[name + "_Def"];
    if (!fn) throw new Error("no _Def for " + name);
    return fn();
  }
  function nameOfCtor(c) {
    if (!ctorName.has(c)) {
      for (const ns of ["GameDef", "BuildRoom", "Build", "Battle"]) loadNs(ns);
    }
    const n = ctorName.get(c);
    if (!n) throw new Error("unknown refCls");
    return n;
  }

  function listItems(j) {
    if (Array.isArray(j)) return j;
    if (!j || typeof j !== "object") return [];
    const n = j._length != null ? j._length : Object.keys(j).filter((k) => /^\d+$/.test(k)).length;
    const out = [];
    for (let i = 0; i < n; i++) out.push(j[String(i)]);
    return out;
  }

  function value(v, bt, refCls) {
    if (v == null) return v;
    if (refCls) return build(nameOfCtor(refCls), v);
    return v;
  }

  function build(name, json) {
    const Cls = classOf(name);
    const inst = new Cls();
    const def = defOf(name);
    def.getValues().forEach((f) => {
      const v = json[f.n];
      if (v === undefined || v === null) return;
      if (f.ft === PF.Repeated) {
        const l = new List();
        listItems(v).forEach((it) => l.push(value(it, f.bt, f.refCls)));
        inst[f.n] = l;
      } else if (f.ft === PF.Map) {
        const d = new Dictionary();
        const ks = listItems(v._keyList), vs = listItems(v._valueList);
        ks.forEach((k, i) => d.setValue(k, value(vs[i], f.vbt, f.vrefCls)));
        inst[f.n] = d;
      } else {
        inst[f.n] = value(v, f.bt, f.refCls);
      }
    });
    return inst;
  }

  return { build, listItems };
}

module.exports = { makeRebuilder };

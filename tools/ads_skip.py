"""Manual ads test harness: drive `CommonModule.showAdvertise` in a real client
without the real SDK, and trace every ads-related message.

Reference: docs/client/SHOW_ADVERTISE.md (flow, message ids, known pitfalls).

    uv run python tools/ads_skip.py [--profile .tmp/pmain] [--cn] [--url URL]

- Opens the game in a persistent browser profile (default `.tmp/pmain` — reuse the
  main repo's logged-in profile with `--profile ../burrito-bison-bot/.tmp/pmain`).
  Do not run two runners on the same profile at once.
- Hooks `SocketMgr.send`, the AdvertiseProxy/LoginGameProxy response handlers and
  PingR so every ads message (module 20, Ping 2/8, PingR 2/9) and every registered
  callback invocation is printed and logged to `.tmp/ads_skip/events-<ts>.jsonl`.
- Clicking ad buttons by hand in the game window goes through the same hooks.
- Terminal commands:

    info [id]     ads config x server data per id (leftTimes/lastTime/cd/cost),
                  view card, AdsFree/AdsClose/isAdvertise perform flags
    watch <id>    stub `sdk.showAds` -> sync SUCCESS then call showAdvertise;
                  SUCCESS lands in `_adCB` and only fires when PingR arrives
    free on|off   override perform AdsFree so any ad button resolves SUCCESS
                  without the SDK (then click the button by hand)
    jump <id>     send JumpAdvertiseRequest directly (AdsClose path); reports
                  whether its request callback ever fires and `_waitingAdsCheck`
                  state, then unsticks the flag (the 7125c handler never calls it)
    ping          send PingRequest with a probe callback
    state         stub/override flags, `_waitingAdsCheck`, `_adCB` length, probes
    reset         restore SDK/perform hooks, clear `_waitingAdsCheck` and `_adCB`
    quit          close the browser and exit

On builds with the showAdvertise early return (e.g. ygkksy) `watch` resolves
SUCCESS immediately with no socket activity — the hooks stay silent on purpose.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

CN_URL = "https://hauntheroesweb.acenetgame.com/"
VN_URL = "https://hauntedroomvnh5.joynetgame.com/"
DEFAULT_PROFILE_DIR = Path(".tmp/pmain")
DEFAULT_OUT_DIR = Path(".tmp/ads_skip")

# PerformType values from the bundle: isAdvertise=39, AdsClose=119, AdsFree=120.
ADS_FREE_PERFORM = 120

BOOTSTRAP = """(() => {
  const require = window.__require;
  if (!require) return;
  if (window.__adsSkip && window.__adsSkip.ready) return;
  const SocketMgr = require("SocketMgr").SocketMgr.prototype;
  const CommonModule = require("CommonModule").CommonModule.Ins;
  const SDKMgr = require("SDKMgr").SDKMgr.Ins;
  const AdvertiseProxy = require("AdvertiseProxy").AdvertiseProxy.Ins;
  const LoginGameProxy = require("LoginGameProxy").LoginGameProxy.Ins;
  const ActivityUtilsModule = require("ActivityUtilsModule").ActivityUtilsModule.Ins;
  const TimerManager = require("TimerManager").TimerManager.Ins;
  const AdsLO = require("AdsLO").AdsLO;
  const TARGET_HANDLERS = [
    "GetAdvertiseInfoRResponse", "JumpAdvertiseRResponse", "InsertRecordRResponse",
    "AdvertiseInfoPPush", "AdvertiseResetInfoPPush", "PingRResponse",
  ];
  const state = {
    ready: false, jumpCBFired: false, pingCBFired: false,
    record: (kind, msg, obj) => {
      try { window.__recordAdsSkip(JSON.stringify({ kind, data: { msg, obj } })).catch(() => {}); } catch {}
    },
    adCBLength: () => {
      const list = CommonModule._adCB;
      return list ? (list._length != null ? list._length : list.length || 0) : -1;
    },
    rowFor: (id) => AdsLO.get(id),
    keyOf: (row, id) => (row && row.key != null ? row.key : id),
    costOf: (row) => {
      try { const cost = JSON.parse(row.cost || "null"); return cost && cost[0] ? cost[0] : null; } catch { return null; }
    },
    info(id) {
      const rows = [];
      // AdsLO.store.foreach passes (key, row) — the key is the id server data uses.
      const collect = (id, row) => {
        const server = CommonModule.getAdvertiseInfo(id);
        rows.push({
          id, key: row.key, cd: row.cd, refresh: row.refresh,
          initTimes: row.initTimes, productId: row.productId || null, cost: this.costOf(row),
          leftTimes: server ? server.leftTimes : null, lastTime: server ? server.lastTime : null,
        });
      };
      if (id != null) {
        const row = this.rowFor(id);
        if (!row) return { error: `AdsLO has no row ${id}` };
        collect(id, row);
      } else {
        AdsLO.store.foreach((key, row) => collect(key, row));
      }
      const perform = (key, dflt) => { try { return SDKMgr.getPerformConfig(key, dflt); } catch { return null; } };
      return {
        serverTime: (() => { try { return TimerManager.getServerTime(); } catch { return null; } })(),
        viewCard: (() => { try { return !!ActivityUtilsModule.isViewCardInEffect; } catch { return null; } })(),
        isAdvertise: perform(39, 1), adsFree: perform(120, false), adsClose: perform(119, false),
        rows,
      };
    },
    watch(id) {
      const row = this.rowFor(id);
      if (!row) return Promise.resolve({ error: `AdsLO has no row ${id}` });
      const key = this.keyOf(row, id);
      const sdk = SDKMgr.sdk;
      if (!sdk) return Promise.resolve({ error: "SDKMgr.Ins.sdk not ready" });
      if (!sdk.__adsSkipOrigShowAds) {
        sdk.__adsSkipOrigShowAds = sdk.showAds;
        sdk.showAds = (params, cb) => {
          this.record("sdk", "stubbed showAds -> SUCCESS(3)", { id: params && params.id });
          if (cb) cb(3);
        };
      }
      return new Promise((resolve) => {
        let done = false;
        const finish = (result) => { if (!done) { done = true; resolve(result); } };
        CommonModule.showAdvertise(key, { id: key, scene: row.scene }, (status) => {
          finish({ status, adCB: this.adCBLength(), key,
                   note: status === 3 ? "queued in _adCB; fires when PingR(2/9) arrives" : "not queued" });
        });
        setTimeout(() => finish({ status: null, adCB: this.adCBLength(), key,
                                  note: "no callback within 5s (exhausted/cooldown/missing-data branch)" }), 5000);
      });
    },
    free(on) {
      if (on) {
        if (!SDKMgr.__adsSkipOrigGPC) {
          SDKMgr.__adsSkipOrigGPC = SDKMgr.getPerformConfig;
          SDKMgr.getPerformConfig = function (key, dflt) {
            if (key === """ + str(ADS_FREE_PERFORM) + """) return true;
            return SDKMgr.__adsSkipOrigGPC.call(this, key, dflt);
          };
        }
        return { adsFreeOverride: true };
      }
      if (SDKMgr.__adsSkipOrigGPC) {
        SDKMgr.getPerformConfig = SDKMgr.__adsSkipOrigGPC;
        delete SDKMgr.__adsSkipOrigGPC;
      }
      return { adsFreeOverride: false };
    },
    jump(id) {
      const row = this.rowFor(id);
      if (!row) return { error: `AdsLO has no row ${id}` };
      const key = this.keyOf(row, id);
      this.jumpCBFired = false;
      const before = CommonModule._waitingAdsCheck === true;
      AdvertiseProxy.JumpAdvertiseRequest({ advertiseType: key }, [() => {
        this.jumpCBFired = true;
        this.record("cb", "JumpAdvertise request callback fired", { advertiseType: key });
      }]);
      return { advertiseType: key, waitingAdsCheckBefore: before };
    },
    ping() {
      this.pingCBFired = false;
      LoginGameProxy.PingRequest([() => {
        this.pingCBFired = true;
        this.record("cb", "PingR request callback fired", {});
      }]);
      return { pingSent: true };
    },
    state() {
      const sdk = SDKMgr.sdk;
      return {
        showAdsStubbed: !!(sdk && sdk.__adsSkipOrigShowAds),
        adsFreeOverride: !!SDKMgr.__adsSkipOrigGPC,
        waitingAdsCheck: CommonModule._waitingAdsCheck === true,
        adCB: this.adCBLength(),
        jumpCBFired: this.jumpCBFired, pingCBFired: this.pingCBFired,
      };
    },
    _resetWaitingFlag: () => { CommonModule._waitingAdsCheck = false; },
    reset() {
      const sdk = SDKMgr.sdk;
      if (sdk && sdk.__adsSkipOrigShowAds) {
        sdk.showAds = sdk.__adsSkipOrigShowAds;
        delete sdk.__adsSkipOrigShowAds;
      }
      this.free(false);
      CommonModule._waitingAdsCheck = false;
      if (CommonModule._adCB && CommonModule._adCB.clear) CommonModule._adCB.clear();
      this.jumpCBFired = this.pingCBFired = false;
      return this.state();
    },
  };
  // Response handlers are registered as bound methods on the SocketMgr dispatch
  // table, so hooking must cover both timings: prototype patching (proxy not yet
  // constructed) and a sweep of the registered table (already bound originals).
  const makeHandlerWrapper = (original, label) => {
    const wrapped = function (data, callbacks, cmd) {
      if (Array.isArray(callbacks) && typeof callbacks[0] === "function") {
        const userCB = callbacks[0];
        callbacks[0] = (...args) => {
          state.record("cb", `${label} request callback fired`, { err: data && data.err });
          return userCB.apply(this, args);
        };
      }
      const result = original.apply(this, [data, callbacks, cmd]);
      state.record("s2c", label, data);
      return result;
    };
    wrapped.__adsSkipHooked = true;
    return wrapped;
  };
  const wrapPrototype = (owner, name) => {
    const label = name.replace("Response", "").replace("Push", "");
    if (!owner[name] || owner[name].__adsSkipHooked) return;
    owner[name] = makeHandlerWrapper(owner[name], label);
  };
  TARGET_HANDLERS.forEach((name) => {
    try { wrapPrototype(AdvertiseProxy, name); } catch {}
    try { wrapPrototype(LoginGameProxy, name); } catch {}
  });
  const sweepRegistered = () => {
    const dic = SocketMgr._responseDic;
    if (!dic || !dic.length) return;
    for (let i = 0; i < dic.length; i++) {
      const entry = dic.getValueByIndex && dic.getValueByIndex(i);
      const bound = entry && entry.response;
      if (!bound || typeof bound !== "function" || bound.__adsSkipHooked) continue;
      const name = (bound.name || "").replace("bound ", "");
      if (!TARGET_HANDLERS.includes(name)) continue;
      entry.response = makeHandlerWrapper(bound, name.replace("Response", "").replace("Push", ""));
    }
  };
  try { sweepRegistered(); } catch {}
  const socketSend = SocketMgr.send;
  SocketMgr.send = function (module, command, data) {
    if (module === 20 || (module === 2 && (command === 8 || command === 9))) {
      try { state.record("c2s", `${this.getCmdName(module, command)}(${module}/${command})`, data); } catch {}
    }
    return socketSend.apply(this, arguments);
  };
  window.__adsSkip = state;
  state.ready = true;
})()"""


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual harness for the ads flow of a real client "
        "(see docs/client/SHOW_ADVERTISE.md)."
    )
    parser.add_argument(
        "--profile",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent browser profile directory (default: %(default)s). "
        "Cookies and login session are kept here.",
    )
    server = parser.add_mutually_exclusive_group()
    server.add_argument("--cn", action="store_true", help="Open the CN server (VN by default).")
    parser.add_argument("--url", help="Override the game entry URL.")
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR),
        help="Directory for events-<ts>.jsonl logs (default: %(default)s).",
    )
    args = parser.parse_args(argv)
    if args.url is None:
        args.url = CN_URL if args.cn else VN_URL
    return args


def pretty(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


async def repl(page, out_path: Path) -> None:
    commands = "info [id] | watch <id> | free on|off | jump <id> | ping | state | reset | quit"
    print(f"commands: {commands}\nlogs: {out_path}", flush=True)
    queue: asyncio.Queue = asyncio.Queue()

    def read_stdin() -> None:
        for line in sys.stdin:
            loop.call_soon_threadsafe(queue.put_nowait, line.strip())

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, read_stdin)
    while True:
        if page.is_closed():
            print("browser closed, exiting", flush=True)
            return
        try:
            raw = await asyncio.wait_for(queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        cmd, _, arg = raw.partition(" ")
        cmd = cmd.lower().strip()
        arg = arg.strip()
        try:
            if cmd == "quit":
                return
            if cmd == "info":
                result = await page.evaluate(
                    "id => window.__adsSkip.info(id != '' ? Number(id) : null)", arg
                )
            elif cmd == "watch":
                result = await page.evaluate("id => window.__adsSkip.watch(Number(id))", int(arg))
            elif cmd == "free":
                result = await page.evaluate("on => window.__adsSkip.free(on === 'on')", arg.lower())
            elif cmd == "jump":
                result = await page.evaluate("id => window.__adsSkip.jump(Number(id))", int(arg))
                await asyncio.sleep(3)
                after = await page.evaluate(
                    "() => ({ jumpCBFired: window.__adsSkip.jumpCBFired,"
                    " waitingAdsCheck: window.__adsSkip.state().waitingAdsCheck })"
                )
                if not after["jumpCBFired"]:
                    await page.evaluate("() => { window.__adsSkip.state()._resetWaitingFlag(); }")
                    after["waitingAdsCheck"] = "reset to false (callback never fired)"
                result = {**result, "after 3s": after}
            elif cmd == "ping":
                result = await page.evaluate("() => window.__adsSkip.ping()")
                await asyncio.sleep(3)
                result = {
                    **result,
                    "pingCBFired": await page.evaluate("() => window.__adsSkip.pingCBFired"),
                }
            elif cmd == "state":
                result = await page.evaluate("() => window.__adsSkip.state()")
            elif cmd == "reset":
                result = await page.evaluate("() => window.__adsSkip.reset()")
            else:
                result = {"error": f"unknown command {cmd!r}", "commands": commands}
        except ValueError:
            result = {"error": f"{cmd} expects a numeric id"}
        except Exception as exc:  # page closed mid-command, JS error, ...
            result = {"error": f"{type(exc).__name__}: {exc}"}
        print(pretty(result), flush=True)
        with out_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps({"kind": "repl", "data": {"msg": raw, "obj": result}}) + "\n")


async def main(argv=None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"events-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    profile_dir = Path(args.profile)
    profile_dir.mkdir(parents=True, exist_ok=True)

    def record(source, payload: str) -> None:
        event = json.loads(payload)
        print(f"[{event['kind']}] {event['data']['msg']} {pretty(event['data']['obj'])}", flush=True)
        with out_path.open("a", encoding="utf-8") as log:
            log.write(payload + "\n")

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            str(profile_dir),
            channel="chrome",
            headless=False,
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
            service_workers="block",
        )
        context.expose_binding("__recordAdsSkip", record)
        context.add_init_script("setInterval(() => { try { " + BOOTSTRAP + " } catch {} }, 150)")
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(args.url, wait_until="domcontentloaded")
        await page.bring_to_front()
        await page.wait_for_function("window.__adsSkip && window.__adsSkip.ready", timeout=120_000)
        print("READY — hooks installed; log in if the profile has no session yet.", flush=True)
        try:
            await repl(page, out_path)
        finally:
            await context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

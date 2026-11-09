"""Standalone POC: override the server selected by game PHP login."""

import argparse
import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from auth import load_auth, restore_auth
from playwright.async_api import async_playwright

GAME_URL = "https://hauntedroomvnh5.joynetgame.com/"
LOGIN_PATTERN = "https://mg-sea-api.bighost.games/sy_api/game_api.php*"

# Fetch the list using the runtime's signer, with the authenticated PHP identity.
# Do not call AgentMgr.getServerList: its handler mutates selection and emits events.
READ_LIST_JS = """({username, timeout}) => new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('Server list timeout')), timeout);
  const d = new (__require('Dictionary').Dictionary)();
  d.add('action', 'get_AllServerList'); d.add('username', username);
  __require('GameHttp').GameHttp.get(__require('AgentConfig').HostType.GetServer,
    d, (_, text) => {clearTimeout(timer);
      try {resolve(JSON.parse(text));} catch {reject(new Error('Invalid server list'));}
    });
})"""
READ_CHARACTER_JS = """() => {
  const a = __require('AgentMgr').AgentMgr.Ins;
  const p = __require('PlayerModule').PlayerModule.Ins.playerInfo?.info;
  return {selectedServer: String(a.selectServer?.s_id),
    playerServer: String(p?.serverId), playerId: String(p?.playerId),
    loginError: Number(a.loginR?.err || 0), newRole: !!a.loginR?.newRole};
}"""


def choose_server(servers: object, server: int) -> dict:
    if not isinstance(servers, list):
        raise TypeError("Server list is not an array")
    matches = [
        s for s in servers if isinstance(s, dict) and str(s.get("s_id")) == str(server)
    ]
    if len(matches) != 1:
        raise ValueError(f"Server {server} not uniquely present in server list")
    target = matches[0]
    if any(target.get(k) in (None, "") for k in ("area", "s_ip", "sPort")):
        raise ValueError("Target server lacks login metadata")
    status = int(target.get("s_healthStatus", 0))
    if status == 4:
        raise ValueError("Target server is under maintenance")
    if status == 1 and not target.get("playerList"):
        raise ValueError("Target server is full and has no existing character")
    if status not in (1, 2, 3):
        raise ValueError(f"Unknown server health status: {status}")
    return target


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--profile", type=Path, help="Existing persistent Chrome profile"
    )
    source.add_argument(
        "--auth-json", type=Path, help="SDK localStorage JSON (read only)"
    )
    parser.add_argument("--acc", help="Exact email key in allLoginList.value")
    parser.add_argument(
        "--server", "--sv", required=True, type=int, help="Target s_id, e.g. 829"
    )
    parser.add_argument("--browser", choices=("chrome", "chromium"), default="chrome")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep browser open after verification until Ctrl+C",
    )
    parser.add_argument(
        "--timeout", type=float, default=120, help="Total login timeout in seconds"
    )
    parser.add_argument(
        "--out", type=Path, help="New output directory; default .tmp/sv-switch/run-..."
    )
    args = parser.parse_args(argv)
    if bool(args.auth_json) != bool(args.acc):
        parser.error("--auth-json and --acc must be supplied together")
    if args.server <= 0 or args.timeout <= 0:
        parser.error("--server and --timeout must be positive")
    if args.profile is not None and not args.profile.is_dir():
        parser.error("--profile must point to an existing profile directory")
    return args


async def run(args):
    auth = load_auth(args.auth_json, args.acc) if args.auth_json else None
    if args.out:
        out = args.out
        out.mkdir(parents=True, exist_ok=False, mode=0o700)
    else:
        root = Path(".tmp/sv-switch")
        root.mkdir(parents=True, exist_ok=True)
        out = Path(
            tempfile.mkdtemp(
                prefix="run-" + datetime.now().strftime("%Y%m%d-%H%M%S-"), dir=root
            )
        )
    result = {
        "targetServer": str(args.server),
        "mode": "fresh-auth" if auth else "profile",
        "success": False,
        "overrides": [],
        "defaultSelectionWrites": 0,
    }
    def write_result():
        (out / "result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )

    print(f"[out] {out}", flush=True)
    async with async_playwright() as pw:
        browser = context = None
        failure = asyncio.get_running_loop().create_future()
        try:
            options = {
                "viewport": {"width": 640, "height": 720},
                "service_workers": "block",
            }
            launch = {
                "channel": None if args.browser == "chromium" else args.browser,
                "headless": args.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--hide-crash-restore-bubble",
                ],
            }
            if auth:
                browser = await pw.chromium.launch(**launch)
                context = await browser.new_context(**options)
                auth_page = await restore_auth(context, *auth, args.acc)
                page = await context.new_page()
            else:
                context = await pw.chromium.launch_persistent_context(
                    str(args.profile), **launch, **options
                )
                auth_page = None
                page = context.pages[0] if context.pages else await context.new_page()

            async def intercept(route):
                request = route.request
                if parse_qs(urlsplit(request.url).query).get("action") != ["login"]:
                    await route.continue_()
                    return
                try:
                    response = await route.fetch(
                        timeout=args.timeout * 1000, max_redirects=0
                    )
                    if not response.ok:
                        raise ValueError(f"PHP login HTTP status {response.status}")
                    data = await response.json()
                    if (
                        data.get("success") != 0
                        or not data.get("game_uin")
                        or not data.get("t_token")
                    ):
                        raise ValueError("PHP login failed or missing identity/token")
                    servers = await page.evaluate(
                        READ_LIST_JS,
                        {
                            "username": data["game_uin"],
                            "timeout": min(args.timeout * 1000, 30000),
                        },
                    )
                    target = choose_server(servers, args.server)
                    before = data.get("svrListT")
                    original = (
                        [str(x.get("s_id")) for x in before if isinstance(x, dict)]
                        if isinstance(before, list)
                        else []
                    )
                    data["svrListT"] = [target]
                    await route.fulfill(response=response, json=data)
                    result["overrides"].append(
                        {
                            "originalServers": original,
                            "targetServer": str(args.server),
                            "area": str(target["area"]),
                            "hasCharacter": bool(target.get("playerList")),
                        }
                    )
                    print(
                        f"[switch] {original} -> {args.server}; existing character: {bool(target.get('playerList'))}",
                        flush=True,
                    )
                except Exception as exc:  # noqa: BLE001 — fail closed and redact browser errors
                    # Never release the original login response on failure: that would
                    # silently log into the wrong server.
                    if not failure.done():
                        failure.set_result(
                            str(exc) if type(exc) is ValueError else type(exc).__name__
                        )
                    await route.abort()

            def on_request(request):
                if parse_qs(urlsplit(request.url).query).get("action") == [
                    "set_switchServer"
                ]:
                    result["defaultSelectionWrites"] += 1

            context.on("request", on_request)
            await context.route(LOGIN_PATTERN, intercept)

            async def verify():
                await page.goto(
                    GAME_URL, wait_until="commit", timeout=args.timeout * 1000
                )
                await page.wait_for_function(
                    """() => {try {
                  return Number(__require('PlayerModule').PlayerModule.Ins.playerInfo?.info?.serverId) > 0;
                } catch {return false;}}""",
                    timeout=args.timeout * 1000,
                )
                state = await page.evaluate(READ_CHARACTER_JS)
                result["character"] = state
                if (
                    not result["overrides"]
                    or state["playerServer"] != str(args.server)
                    or state["selectedServer"] != str(args.server)
                    or state["loginError"]
                ):
                    raise ValueError(
                        "Backend character server does not match requested server"
                    )
                if auth:
                    matched = False
                    for frame in page.frames:
                        if urlsplit(frame.url).netloc == "h5sdk.joynetgame.com":
                            matched = (
                                await frame.evaluate(
                                    "k => JSON.parse(localStorage.getItem(k))?.value?.username",
                                    auth[1],
                                )
                                == args.acc
                            )
                            if matched:
                                break
                    if not matched:
                        raise ValueError("SDK account verification failed")
                result["success"] = True

            verification = asyncio.create_task(verify())
            try:
                done, _ = await asyncio.wait(
                    [verification, failure],
                    timeout=args.timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if failure in done:
                    raise ValueError(f"Login override failed ({failure.result()})")
                if verification not in done:
                    raise TimeoutError("Login verification timed out")
                await verification
            finally:
                if not verification.done():
                    verification.cancel()
                    await asyncio.gather(verification, return_exceptions=True)
            if auth_page:
                await auth_page.close()
            print(
                f"[verified] backend character server={result['character']['playerServer']}; newRole={result['character']['newRole']}",
                flush=True,
            )
            if args.keep_open:
                # Result must exist on disk while the browser is held open.
                write_result()
                print("[open] Ctrl+C to close", flush=True)
                await asyncio.Event().wait()
        except Exception as exc:  # noqa: BLE001 — fail closed and redact browser errors
            result["success"] = False
            # Browser exceptions can embed authenticated URLs; keep diagnostic output
            # to a type and our own validation messages.
            result["error"] = (
                str(exc)
                if isinstance(exc, (ValueError, TimeoutError))
                else type(exc).__name__
            )
            print(f"[failed] {result['error']}", flush=True)
        finally:
            write_result()
            if context:
                await context.close()
            if browser:
                await browser.close()
    return result["success"]


def main():
    args = parse_args()
    try:
        ok = asyncio.run(run(args))
    except KeyboardInterrupt:
        return
    except (ValueError, TypeError, OSError) as exc:
        raise SystemExit(
            f"[failed] {type(exc).__name__}: check auth JSON and output/profile paths"
        ) from None
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

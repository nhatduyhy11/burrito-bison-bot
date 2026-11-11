"""Locked-down Chromium for the sandbox: throwaway profile, service workers blocked, and nothing but the
mirror origin reachable (other requests aborted and logged, WebSockets closed)."""

import re
from dataclasses import dataclass, field


@dataclass
class Capture:
    """What the page did during a run that the report cares about."""
    blocked: list = field(default_factory=list)
    page_errors: list = field(default_factory=list)
    console_errors: list = field(default_factory=list)

    def clear(self):
        for seen in (self.blocked, self.page_errors, self.console_errors):
            seen.clear()


async def launch(pw, profile_dir, *, origin, cdp_port, channel, headless, size, record, emit, profile_json):
    """Open the sandbox browser on `profile_dir`. `size` is "WxH"; `record` a video directory or None;
    `emit(kind, msg)` writes the run log; `profile_json()` returns the formation profile to serve as
    /__sim/active-profile.json (None = let the mirror answer). Returns (context, page, capture)."""
    viewport = dict(zip(("width", "height"), map(int, size.split("x"))))
    ctx = await pw.chromium.launch_persistent_context(
        profile_dir,
        channel=channel,
        headless=headless,
        # Portrait game (design 720x1280, FIXED_WIDTH): a landscape window only shows a
        # 720x400 strip. Headed defaults to the hauntedroom runner's 640x720.
        viewport=viewport,
        service_workers="block",
        **({"record_video_dir": record, "record_video_size": viewport} if record else {}),
        args=[f"--remote-debugging-port={cdp_port}", "--remote-debugging-address=127.0.0.1"],
    )
    cap = Capture()
    active_profile = origin + "/__sim/active-profile.json"

    async def guard(route):
        url = route.request.url
        profile = profile_json()
        if profile is not None and url == active_profile:
            await route.fulfill(json=profile)
        elif url.startswith(origin + "/"):
            await route.continue_()
        else:
            cap.blocked.append(url)
            emit("BLOCKED", f"{route.request.method} {url}")
            await route.abort("blockedbyclient")

    async def ws_guard(ws):
        cap.blocked.append("ws " + ws.url)
        emit("BLOCKED", f"WS {ws.url}")
        await ws.close()

    await ctx.route("**/*", guard)
    await ctx.route_web_socket(re.compile(".*"), ws_guard)
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    def on_console(m):
        emit(f"console.{m.type}", m.text)
        if m.type == "error":
            cap.console_errors.append(m.text)

    def on_pageerror(e):
        emit("pageerror", str(e))
        cap.page_errors.append(str(e))

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    return ctx, page, cap

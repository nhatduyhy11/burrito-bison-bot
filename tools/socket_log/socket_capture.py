"""POC: capture Haunted Room WebSocket frames while walking the mine-history flow.

Launches the same persistent-profile browser as ``hauntedroom_runner.py``, hooks
every WebSocket on every page, and dumps each frame verbatim (binary included)
so the mine-history protocol can be reverse engineered from a single session.

Usage:
    uv run python tools/socket_log/socket_capture.py --profile .tmp/m535 \
        --step sleep:8 --step shot:01_loaded --step click:463,218 ...

Step DSL:
    sleep:S      wait S seconds (float ok)
    shot:NAME    save out_dir/screens/NAME.png
    click:X,Y    left-click at page coordinates
    mark:LABEL   write a marker line into index.jsonl (correlate frames later)
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from playwright.async_api import Page, async_playwright

sys.path.insert(0, str(Path(__file__).parent))

from navigation import navigate_to_game  # noqa: E402
from page_guards import (  # noqa: E402
    install_game_core_frame_guard_after_delay,
    install_profile_popup_guard,
)

DEFAULT_OUT_DIR = Path(".tmp/socket-capture")


class FrameWriter:
    """Persist every WebSocket payload plus an index for later correlation."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.frames_dir = out_dir / "frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = out_dir / "index.jsonl"
        self.seq = 0
        self.started = time.monotonic()
        self._lock = asyncio.Lock()

    async def _append(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False)
        async with self._lock:
            with self.index_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started) * 1000)

    async def mark(self, label: str) -> None:
        await self._append(
            {"n": None, "t": self.elapsed_ms(), "dir": "M", "label": label}
        )
        print(f"[mark] {label} @ {self.elapsed_ms()}ms")

    async def write_frame(self, direction: str, ws_url: str, payload: Union[str, bytes]) -> None:
        self.seq += 1
        seq = self.seq
        if isinstance(payload, str):
            raw = payload.encode("utf-8")
            suffix = ".txt"
        else:
            raw = payload
            suffix = ".bin"
        name = f"{seq:05d}-{direction}{suffix}"
        (self.frames_dir / name).write_bytes(raw)
        await self._append(
            {
                "n": seq,
                "t": self.elapsed_ms(),
                "dir": direction,
                "ws": ws_url,
                "size": len(raw),
                "file": f"frames/{name}",
            }
        )
        preview = raw[:48].hex() if suffix == ".bin" else raw[:48].decode("utf-8", "replace")
        print(f"[ws {direction}] #{seq} {len(raw)}B {preview}")


def attach_capture(page: Page, writer: FrameWriter) -> None:
    def on_websocket(ws) -> None:
        print(f"[ws open] {ws.url}")
        asyncio.ensure_future(
            writer._append({"n": None, "t": writer.elapsed_ms(), "dir": "O", "ws": ws.url})
        )
        ws.on("framesent", lambda payload: asyncio.ensure_future(writer.write_frame("S", ws.url, payload)))
        ws.on(
            "framereceived",
            lambda payload: asyncio.ensure_future(writer.write_frame("R", ws.url, payload)),
        )

    page.on("websocket", on_websocket)


def parse_step(spec: str) -> tuple[str, str]:
    verb, _, arg = spec.partition(":")
    return verb.strip().lower(), arg


async def run_step(page, writer: FrameWriter, verb: str, arg: str, out_dir: Path) -> None:
    if verb == "sleep":
        await asyncio.sleep(float(arg))
    elif verb == "shot":
        path = out_dir / "screens" / f"{arg}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(path))
        print(f"[shot] {path}")
    elif verb == "click":
        x_s, _, y_s = arg.partition(",")
        await page.mouse.click(int(x_s), int(y_s))
        print(f"[click] ({x_s},{y_s})")
        await asyncio.sleep(1.0)
    elif verb == "mark":
        await writer.mark(arg)
    else:
        raise ValueError(f"Unknown step: {verb}:{arg}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=".tmp/m535")
    parser.add_argument("--url", default="https://hauntedroomvnh5.joynetgame.com/")
    parser.add_argument("--out", default=None, help="Output dir (default .tmp/socket-capture/run-<ts>)")
    parser.add_argument("--settle", type=float, default=6.0, help="Seconds to wait after navigation")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--browser", default="chrome")
    parser.add_argument("--step", action="append", default=[], help="Step DSL, repeatable")
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc)
    out_dir = Path(args.out) if args.out else DEFAULT_OUT_DIR / f"run-{started_at:%Y%m%d-%H%M%S}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta.json").write_text(
        json.dumps(
            {
                "url": args.url,
                "profile": args.profile,
                "started_at": started_at.isoformat(),
                "steps": args.step,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    writer = FrameWriter(out_dir)

    async with async_playwright() as playwright:
        launch_options = {
            "user_data_dir": str(Path(args.profile)),
            "headless": args.headless,
            "viewport": {"width": args.width, "height": args.height},
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--hide-crash-restore-bubble",
            ],
            "service_workers": "block",
        }
        if args.browser != "chromium":
            launch_options["channel"] = args.browser
        context = await playwright.chromium.launch_persistent_context(**launch_options)
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            attach_capture(page, writer)
            context.on("page", lambda p: attach_capture(p, writer))
            page = await navigate_to_game(context, page, args.url, prepare_page=install_profile_popup_guard)
            guard_task = asyncio.create_task(install_game_core_frame_guard_after_delay(page))
            await asyncio.sleep(args.settle)
            for spec in args.step:
                verb, arg = parse_step(spec)
                await run_step(page, writer, verb, arg, out_dir)
            if writer.seq:
                print(f"[done] captured {writer.seq} frames -> {out_dir}")
            guard_task.cancel()
        finally:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())

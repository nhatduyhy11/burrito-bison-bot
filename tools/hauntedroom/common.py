import argparse
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

GAME_URL = "https://hauntedroomvnh5.joynetgame.com/"
DEFAULT_VIEWPORT_WIDTH = 640
DEFAULT_VIEWPORT_HEIGHT = 720
DEFAULT_BROWSER = "chrome"

ACTION_LOOP_COUNT = 0

LOAD_WAIT_MS = 16000
COUNTDOWN_WAIT_THRESHOLD_MS = 10000

DEFAULT_PROFILE_DIR = Path(".tmp/hauntedroom-profile")
TIMEOUT_SCREENSHOT_DIR = Path(".tmp/hauntedroom-timeouts")
HOTKEY_SCRIPT = """
() => {
    if (window.__hauntedRoomHotkeysInstalled) {
        return;
    }

    window.__hauntedRoomHotkeysInstalled = true;
    window.addEventListener(
        "keydown",
        (event) => {
            if (
                !event.shiftKey ||
                event.ctrlKey ||
                event.altKey ||
                event.metaKey ||
                event.repeat ||
                !/^Digit(?:[0-7]|9)$/.test(event.code)
            ) {
                return;
            }

            event.preventDefault();
            event.stopImmediatePropagation();
            window.sendHauntedRoomCommand(event.code.slice(-1));
        },
        true
    );
}
"""


def prepare_runner(
    action_loader: Callable[[Path], list[dict]],
) -> tuple[argparse.Namespace, list[dict], Path]:
    parser = argparse.ArgumentParser(
        description=(
            "Run template/click/wait automation for Haunted Room in a "
            "persistent browser profile."
        )
    )
    parser.add_argument(
        "--actions",
        default="tools/hauntedroom_actions.sample.json",
        help="JSON file containing template, blocker, click, or wait actions.",
    )
    parser.add_argument(
        "--profile",
        default=str(DEFAULT_PROFILE_DIR),
        help=(
            "Persistent browser profile directory. "
            "Cookies and local storage are kept here."
        ),
    )
    parser.add_argument("--url", default=GAME_URL)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--browser",
        choices=("chrome", "msedge", "chromium"),
        default=DEFAULT_BROWSER,
        help=(
            "Browser channel to use. Chrome and Edge are discovered by Playwright "
            "on the current OS; chromium requires a Playwright-managed browser install."
        ),
    )
    parser.add_argument("--width", type=int, default=DEFAULT_VIEWPORT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_VIEWPORT_HEIGHT)
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep the browser open after actions finish.",
    )
    args = parser.parse_args()

    # Standby mode still needs the actions so a hotkey can start the flow later.
    actions = action_loader(Path(args.actions))
    profile_dir = Path(args.profile)
    profile_dir.mkdir(parents=True, exist_ok=True)
    return args, actions, profile_dir


async def save_timeout_screenshot(page, label: str) -> Optional[Path]:
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-_")
    safe_label = safe_label or "timeout"
    if safe_label.lower().endswith(".png"):
        safe_label = safe_label[:-4]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    screenshot_path = TIMEOUT_SCREENSHOT_DIR / f"{timestamp}-{safe_label}.png"
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        await page.screenshot(
            path=str(screenshot_path),
            type="png",
            scale="css",
        )
    except Exception as error:
        print(f"Failed to save timeout screenshot: {error}", flush=True)
        return None

    resolved_path = screenshot_path.resolve()
    print(f"Timeout screenshot saved: {resolved_path}", flush=True)
    return resolved_path


async def wait_with_countdown(
    page,
    ms: int,
    label: str,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    if ms <= COUNTDOWN_WAIT_THRESHOLD_MS:
        print(f"{label}: wait {ms}ms")
    remaining_ms = ms
    while remaining_ms > 0:
        if stop_event is not None and stop_event.is_set():
            return False
        if ms > COUNTDOWN_WAIT_THRESHOLD_MS:
            remaining_seconds = (remaining_ms + 999) // 1000
            print(f"{label}: wait {remaining_seconds}s remaining")
        step_ms = min(250, remaining_ms)
        await page.wait_for_timeout(step_ms)
        remaining_ms -= step_ms
    return stop_event is None or not stop_event.is_set()


async def start_hotkey_listener(
    page,
    command_queue: asyncio.Queue[str],
) -> None:
    async def send_command(source, command: str) -> None:
        command_queue.put_nowait(command)

    await page.expose_binding("sendHauntedRoomCommand", send_command)
    await page.add_init_script(HOTKEY_SCRIPT)
    for frame in page.frames:
        await frame.evaluate(HOTKEY_SCRIPT)


async def start_user_click_logger(page) -> None:
    async def log_click(source, click: dict) -> None:
        action = {
            "type": "click",
            "x": int(click["x"]),
            "y": int(click["y"]),
            "button": click.get("button", "left"),
        }
        print(json.dumps(action, separators=(", ", ": ")))

    await page.expose_binding("logHauntedRoomClick", log_click)
    await page.evaluate(
        """
        () => {
            if (window.__hauntedRoomClickLoggerInstalled) {
                return;
            }

            window.__hauntedRoomClickLoggerInstalled = true;
            window.__hauntedRoomSuppressNextClickLog = false;

            window.addEventListener(
                "click",
                (event) => {
                    if (window.__hauntedRoomSuppressNextClickLog) {
                        window.__hauntedRoomSuppressNextClickLog = false;
                        return;
                    }

                    window.logHauntedRoomClick({
                        x: Math.round(event.clientX),
                        y: Math.round(event.clientY),
                        button: event.button === 1
                            ? "middle"
                            : event.button === 2
                                ? "right"
                                : "left",
                    });
                },
                true
            );
        }
        """
    )


async def wait_for_ctrl_c(page, message: str) -> None:
    print(message, flush=True)
    try:
        while True:
            await page.wait_for_timeout(1000)
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("Stopping runner...", flush=True)

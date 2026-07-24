import asyncio
import json
from pathlib import Path

GAME_URL = "https://hauntedroomvnh5.joynetgame.com/"
DEFAULT_VIEWPORT_WIDTH = 640
DEFAULT_VIEWPORT_HEIGHT = 720
DEFAULT_BROWSER = "chrome"

ACTION_LOOP_COUNT = 2

LOAD_WAIT_MS = 16000
COUNTDOWN_WAIT_THRESHOLD_MS = 10000

DEFAULT_PROFILE_DIR = Path(".tmp/hauntedroom-profile")


async def wait_with_countdown(page, ms: int, label: str) -> None:
    if ms <= COUNTDOWN_WAIT_THRESHOLD_MS:
        print(f"{label}: wait {ms}ms")
        await page.wait_for_timeout(ms)
        return

    remaining_ms = ms
    while remaining_ms > 0:
        remaining_seconds = (remaining_ms + 999) // 1000
        print(f"{label}: wait {remaining_seconds}s remaining")
        step_ms = min(1000, remaining_ms)
        await page.wait_for_timeout(step_ms)
        remaining_ms -= step_ms


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

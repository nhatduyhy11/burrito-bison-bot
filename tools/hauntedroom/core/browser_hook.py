"""JavaScript hooks and Python bindings installed into browser pages."""

import asyncio
import json


HOTKEY_SCRIPT = """
() => {
    if (window.__hauntedRoomHotkeysInstalled) {
        return;
    }

    window.__hauntedRoomHotkeysInstalled = true;
    window.addEventListener(
        "keydown",
        (event) => {
            const command = /^Digit[0-9]$/.test(event.code)
                ? event.code.slice(-1)
                : event.code === "KeyT"
                    ? "t"
                    : event.code === "KeyE"
                        ? "e"
                        : null;
            if (
                !event.shiftKey ||
                event.ctrlKey ||
                event.altKey ||
                event.metaKey ||
                event.repeat ||
                command === null
            ) {
                return;
            }

            event.preventDefault();
            event.stopImmediatePropagation();
            window.sendHauntedRoomCommand(command);
        },
        true
    );
}
"""

CLICK_LOGGER_SCRIPT = """
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

SUPPRESS_NEXT_CLICK_LOG_SCRIPT = (
    "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
)


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
    await page.evaluate(CLICK_LOGGER_SCRIPT)


async def suppress_next_click_log(page) -> None:
    """Keep the click logger from recording the next bot-generated click."""
    await page.evaluate(SUPPRESS_NEXT_CLICK_LOG_SCRIPT)

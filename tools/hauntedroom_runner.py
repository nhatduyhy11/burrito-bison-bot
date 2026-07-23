import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

from hauntedroom_common import (
    ACTION_LOOP_COUNT,
    DEFAULT_BROWSER,
    DEFAULT_PROFILE_DIR,
    DEFAULT_VIEWPORT_HEIGHT,
    DEFAULT_VIEWPORT_WIDTH,
    GAME_URL,
    LOAD_WAIT_MS,
    start_user_click_logger,
    wait_for_ctrl_c,
    wait_with_countdown,
)


def load_actions(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        actions = json.load(file)

    if not isinstance(actions, list):
        raise ValueError("Actions file must contain a JSON array.")

    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            raise ValueError(f"Action #{index} must be an object.")

        kind = action.get("type")
        if kind == "click":
            if "x" not in action or "y" not in action:
                raise ValueError(f"Action #{index} click requires x and y.")
        elif kind == "wait":
            if "ms" not in action:
                raise ValueError(f"Action #{index} wait requires ms.")
        else:
            raise ValueError(f"Action #{index} has unsupported type: {kind!r}.")

    return actions


async def run_actions(page, actions: list[dict], loop_count: int = ACTION_LOOP_COUNT) -> None:
    for loop_index in range(1, loop_count + 1):
        print(f"loop {loop_index}/{loop_count} start", flush=True)

        for action_index, action in enumerate(actions, start=1):
            kind = action["type"]

            if kind == "click":
                x = int(action["x"])
                y = int(action["y"])
                button = action.get("button", "left")
                note = action.get("note")
                note_suffix = f" ({note})" if note else ""
                print(f"{loop_index}.{action_index}: click {x},{y}{note_suffix}")
                await page.evaluate("() => { window.__hauntedRoomSuppressNextClickLog = true; }")
                await page.mouse.click(x, y, button=button)
                continue

            ms = int(action["ms"])
            note = action.get("note")
            note_suffix = f" ({note})" if note else ""
            await wait_with_countdown(page, ms, f"{loop_index}.{action_index}{note_suffix}")

        print(f"loop {loop_index}/{loop_count} finish", flush=True)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run simple click/wait automation for Haunted Room in a persistent browser profile."
    )
    parser.add_argument(
        "--actions",
        default="tools/hauntedroom_actions.sample.json",
        help="JSON file containing only click/wait actions.",
    )
    parser.add_argument(
        "--profile",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent browser profile directory. Cookies and local storage are kept here.",
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

    actions = [] if ACTION_LOOP_COUNT == 0 else load_actions(Path(args.actions))
    profile_dir = Path(args.profile)
    profile_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        launch_options = {
            "user_data_dir": str(profile_dir),
            "headless": args.headless,
            "viewport": {"width": args.width, "height": args.height},
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if args.browser != "chromium":
            launch_options["channel"] = args.browser

        context = await playwright.chromium.launch_persistent_context(**launch_options)

        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(args.url, wait_until="domcontentloaded")
            await start_user_click_logger(page)

            if ACTION_LOOP_COUNT == 0:
                await wait_for_ctrl_c(
                    page,
                    "ACTION_LOOP_COUNT is 0; no actions will run. Press Ctrl+C to exit.",
                )
            else:
                await wait_with_countdown(page, LOAD_WAIT_MS, "load")
                await run_actions(page, actions)
                if args.keep_open:
                    await wait_for_ctrl_c(
                        page,
                        "Actions done. Press Ctrl+C to close this runner.",
                    )
        finally:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())

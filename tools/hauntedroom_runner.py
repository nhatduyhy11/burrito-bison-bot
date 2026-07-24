import argparse
import asyncio
import json
from pathlib import Path

import cv2
import numpy as np
from playwright.async_api import async_playwright

from hauntedroom_common import (
    ACTION_LOOP_COUNT,
    DEFAULT_BROWSER,
    DEFAULT_PROFILE_DIR,
    DEFAULT_VIEWPORT_HEIGHT,
    DEFAULT_VIEWPORT_WIDTH,
    GAME_URL,
    start_user_click_logger,
    wait_for_ctrl_c,
    wait_with_countdown,
)


DEFAULT_TEMPLATE_THRESHOLD = 0.9
DEFAULT_TEMPLATE_TIMEOUT_MS = 30_000
DEFAULT_TEMPLATE_POLL_MS = 150
DEFAULT_CLICK_DELAY_MS = 500


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
        elif kind == "click_template":
            template = action.get("template")
            if not isinstance(template, str) or not template:
                raise ValueError(f"Action #{index} click_template requires template.")

            template_path = (path.parent / template).resolve()
            if not template_path.is_file():
                raise ValueError(
                    f"Action #{index} template does not exist: {template_path}"
                )
            action["_template_path"] = template_path

            threshold = float(action.get("threshold", DEFAULT_TEMPLATE_THRESHOLD))
            if not 0 < threshold <= 1:
                raise ValueError(
                    f"Action #{index} threshold must be greater than 0 and at most 1."
                )

            for field in ("timeout_ms", "poll_ms", "delay_ms"):
                if field in action and int(action[field]) < 0:
                    raise ValueError(f"Action #{index} {field} cannot be negative.")
        elif kind == "wait":
            if "ms" not in action:
                raise ValueError(f"Action #{index} wait requires ms.")
        else:
            raise ValueError(f"Action #{index} has unsupported type: {kind!r}.")

    return actions


def load_template(path: Path) -> np.ndarray:
    template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise ValueError(f"OpenCV could not read template: {path}")
    return template


async def capture_page_grayscale(page) -> np.ndarray:
    screenshot = await page.screenshot(type="png", scale="css")
    encoded = np.frombuffer(screenshot, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError("OpenCV could not decode the Playwright screenshot.")
    return image


async def wait_for_template(
    page,
    template: np.ndarray,
    template_name: str,
    threshold: float,
    timeout_ms: int,
    poll_ms: int,
) -> tuple[int, int, float]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_ms / 1000
    best_score = -1.0

    while True:
        screenshot = await capture_page_grayscale(page)
        screenshot_height, screenshot_width = screenshot.shape
        template_height, template_width = template.shape

        if template_width > screenshot_width or template_height > screenshot_height:
            raise ValueError(
                f"Template {template_name!r} is {template_width}x{template_height}, "
                f"larger than screenshot {screenshot_width}x{screenshot_height}."
            )

        result = cv2.matchTemplate(
            screenshot,
            template,
            cv2.TM_CCOEFF_NORMED,
        )
        _, score, _, top_left = cv2.minMaxLoc(result)
        best_score = max(best_score, score)

        if score >= threshold:
            center_x = top_left[0] + template_width // 2
            center_y = top_left[1] + template_height // 2
            return center_x, center_y, score

        if loop.time() >= deadline:
            raise TimeoutError(
                f"Timed out waiting for {template_name!r}; "
                f"best score={best_score:.3f}, threshold={threshold:.3f}."
            )

        await page.wait_for_timeout(poll_ms)


async def run_actions(page, actions: list[dict], loop_count: int = ACTION_LOOP_COUNT) -> None:
    templates = {
        action["_template_path"]: load_template(action["_template_path"])
        for action in actions
        if action["type"] == "click_template"
    }

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

            if kind == "click_template":
                template_path = action["_template_path"]
                threshold = float(
                    action.get("threshold", DEFAULT_TEMPLATE_THRESHOLD)
                )
                timeout_ms = int(
                    action.get("timeout_ms", DEFAULT_TEMPLATE_TIMEOUT_MS)
                )
                poll_ms = int(action.get("poll_ms", DEFAULT_TEMPLATE_POLL_MS))
                delay_ms = int(action.get("delay_ms", DEFAULT_CLICK_DELAY_MS))
                button = action.get("button", "left")
                note = action.get("note")
                note_suffix = f" ({note})" if note else ""

                print(
                    f"{loop_index}.{action_index}: wait for "
                    f"{template_path.name}{note_suffix}",
                    flush=True,
                )
                x, y, score = await wait_for_template(
                    page,
                    templates[template_path],
                    template_path.name,
                    threshold,
                    timeout_ms,
                    poll_ms,
                )
                print(
                    f"{loop_index}.{action_index}: detected "
                    f"{template_path.name} at {x},{y}, score={score:.3f}; "
                    f"click in {delay_ms}ms",
                    flush=True,
                )
                await page.wait_for_timeout(delay_ms)
                await page.evaluate(
                    "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
                )
                await page.mouse.click(x, y, button=button)
                continue

            ms = int(action["ms"])
            note = action.get("note")
            note_suffix = f" ({note})" if note else ""
            await wait_with_countdown(page, ms, f"{loop_index}.{action_index}{note_suffix}")

        print(f"loop {loop_index}/{loop_count} finish", flush=True)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run template/click/wait automation for Haunted Room in a "
            "persistent browser profile."
        )
    )
    parser.add_argument(
        "--actions",
        default="tools/hauntedroom_actions.sample.json",
        help="JSON file containing click_template, click, or wait actions.",
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

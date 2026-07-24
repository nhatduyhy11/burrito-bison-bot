import asyncio
import json
from pathlib import Path

import cv2
import numpy as np
from playwright.async_api import async_playwright

from hauntedroom_common import (
    ACTION_LOOP_COUNT,
    prepare_runner,
    save_timeout_screenshot,
    start_user_click_logger,
    wait_for_ctrl_c,
    wait_with_countdown,
)


DEFAULT_TEMPLATE_THRESHOLD = 0.9
DEFAULT_TEMPLATE_TIMEOUT_MS = 30_000
DEFAULT_TEMPLATE_POLL_MS = 400
DEFAULT_CLICK_DELAY_MS = 500
DEFAULT_CLICK_INTERVAL_MS = 100
SUPPORTED_CLICK_POSITIONS = {"center", "top_middle"}


def validate_threshold(action: dict, index: int) -> None:
    threshold = float(action.get("threshold", DEFAULT_TEMPLATE_THRESHOLD))
    if not 0 < threshold <= 1:
        raise ValueError(
            f"Action #{index} threshold must be greater than 0 and at most 1."
        )


def validate_timing_fields(action: dict, index: int) -> None:
    for field in ("timeout_ms", "poll_ms", "delay_ms", "click_interval_ms"):
        if field in action and int(action[field]) < 0:
            raise ValueError(f"Action #{index} {field} cannot be negative.")


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
            validate_threshold(action, index)
            validate_timing_fields(action, index)
            click_count = int(action.get("click_count", 1))
            if click_count < 1:
                raise ValueError(f"Action #{index} click_count must be at least 1.")
        elif kind == "clear_blockers":
            templates_dir = action.get("templates_dir")
            until_template = action.get("until_template")
            if not isinstance(templates_dir, str) or not templates_dir:
                raise ValueError(
                    f"Action #{index} clear_blockers requires templates_dir."
                )
            if not isinstance(until_template, str) or not until_template:
                raise ValueError(
                    f"Action #{index} clear_blockers requires until_template."
                )

            templates_dir_path = (path.parent / templates_dir).resolve()
            if not templates_dir_path.is_dir():
                raise ValueError(
                    f"Action #{index} blocker directory does not exist: "
                    f"{templates_dir_path}"
                )
            blocker_paths = sorted(templates_dir_path.glob("*.png"))
            if not blocker_paths:
                raise ValueError(
                    f"Action #{index} blocker directory has no PNG files: "
                    f"{templates_dir_path}"
                )

            until_template_path = (path.parent / until_template).resolve()
            if not until_template_path.is_file():
                raise ValueError(
                    f"Action #{index} until_template does not exist: "
                    f"{until_template_path}"
                )

            action["_blocker_paths"] = blocker_paths
            action["_until_template_path"] = until_template_path

            click_positions = action.get("click_positions", {})
            if not isinstance(click_positions, dict):
                raise ValueError(f"Action #{index} click_positions must be an object.")
            blocker_names = {blocker_path.name for blocker_path in blocker_paths}
            for template_name, click_position in click_positions.items():
                if template_name not in blocker_names:
                    raise ValueError(
                        f"Action #{index} click_positions references unknown blocker: "
                        f"{template_name}"
                    )
                if click_position not in SUPPORTED_CLICK_POSITIONS:
                    raise ValueError(
                        f"Action #{index} unsupported click position: {click_position!r}."
                    )
            validate_threshold(action, index)
            validate_timing_fields(action, index)
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
            screenshot_path = await save_timeout_screenshot(page, template_name)
            screenshot_suffix = (
                f", screenshot={screenshot_path}" if screenshot_path else ""
            )
            raise TimeoutError(
                f"Timed out waiting for {template_name!r}; "
                f"best score={best_score:.3f}, threshold={threshold:.3f}"
                f"{screenshot_suffix}."
            )

        await page.wait_for_timeout(poll_ms)


def find_template(
    screenshot: np.ndarray,
    template: np.ndarray,
    template_name: str,
    click_position: str = "center",
) -> tuple[int, int, float]:
    screenshot_height, screenshot_width = screenshot.shape
    template_height, template_width = template.shape
    if template_width > screenshot_width or template_height > screenshot_height:
        raise ValueError(
            f"Template {template_name!r} is {template_width}x{template_height}, "
            f"larger than screenshot {screenshot_width}x{screenshot_height}."
        )

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, top_left = cv2.minMaxLoc(result)
    center_x = top_left[0] + template_width // 2
    if click_position == "top_middle":
        click_y = top_left[1] + min(1, template_height - 1)
    else:
        click_y = top_left[1] + template_height // 2
    return center_x, click_y, score


async def clear_blockers(
    page,
    blocker_paths: list[Path],
    until_template_path: Path,
    templates: dict[Path, np.ndarray],
    threshold: float,
    timeout_ms: int,
    poll_ms: int,
    delay_ms: int,
    click_positions: dict[str, str],
    label: str,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_ms / 1000
    best_until_score = -1.0

    while True:
        screenshot = await capture_page_grayscale(page)

        blocker_matches = []
        for blocker_path in blocker_paths:
            x, y, score = find_template(
                screenshot,
                templates[blocker_path],
                blocker_path.name,
                click_positions.get(blocker_path.name, "center"),
            )
            if score >= threshold:
                blocker_matches.append((score, blocker_path, x, y))

        if blocker_matches:
            score, blocker_path, x, y = max(blocker_matches, key=lambda match: match[0])
            print(
                f"{label}: blocker {blocker_path.name} at {x},{y}, "
                f"score={score:.3f}; click in {delay_ms}ms",
                flush=True,
            )
            await page.wait_for_timeout(delay_ms)
            await page.evaluate(
                "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
            )
            await page.mouse.click(x, y)
            await page.wait_for_timeout(poll_ms)
            deadline = loop.time() + timeout_ms / 1000
            continue

        _, _, until_score = find_template(
            screenshot,
            templates[until_template_path],
            until_template_path.name,
        )
        best_until_score = max(best_until_score, until_score)
        if until_score >= threshold:
            print(
                f"{label}: no blocker; {until_template_path.name} ready "
                f"(score={until_score:.3f})",
                flush=True,
            )
            return

        if loop.time() >= deadline:
            screenshot_path = await save_timeout_screenshot(page, label)
            screenshot_suffix = (
                f", screenshot={screenshot_path}" if screenshot_path else ""
            )
            raise TimeoutError(
                f"{label}: timed out clearing blockers and waiting for "
                f"{until_template_path.name!r}; best score={best_until_score:.3f}, "
                f"threshold={threshold:.3f}{screenshot_suffix}."
            )

        await page.wait_for_timeout(poll_ms)


async def run_actions(page, actions: list[dict], loop_count: int = ACTION_LOOP_COUNT) -> None:
    template_paths: set[Path] = set()
    for action in actions:
        if action["type"] == "click_template":
            template_paths.add(action["_template_path"])
        elif action["type"] == "clear_blockers":
            template_paths.update(action["_blocker_paths"])
            template_paths.add(action["_until_template_path"])
    templates = {path: load_template(path) for path in template_paths}

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

            if kind == "clear_blockers":
                note = action.get("note")
                note_suffix = f" ({note})" if note else ""
                label = f"{loop_index}.{action_index}{note_suffix}"
                await clear_blockers(
                    page,
                    action["_blocker_paths"],
                    action["_until_template_path"],
                    templates,
                    float(action.get("threshold", DEFAULT_TEMPLATE_THRESHOLD)),
                    int(action.get("timeout_ms", DEFAULT_TEMPLATE_TIMEOUT_MS)),
                    int(action.get("poll_ms", DEFAULT_TEMPLATE_POLL_MS)),
                    int(action.get("delay_ms", DEFAULT_CLICK_DELAY_MS)),
                    action.get("click_positions", {}),
                    label,
                )
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
                click_count = int(action.get("click_count", 1))
                click_interval_ms = int(
                    action.get("click_interval_ms", DEFAULT_CLICK_INTERVAL_MS)
                )
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
                    f"click {click_count} time(s) in {delay_ms}ms",
                    flush=True,
                )
                await page.wait_for_timeout(delay_ms)
                for click_index in range(click_count):
                    await page.evaluate(
                        "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
                    )
                    await page.mouse.click(x, y, button=button)
                    if click_index + 1 < click_count:
                        await page.wait_for_timeout(click_interval_ms)
                continue

            ms = int(action["ms"])
            note = action.get("note")
            note_suffix = f" ({note})" if note else ""
            await wait_with_countdown(page, ms, f"{loop_index}.{action_index}{note_suffix}")

        print(f"loop {loop_index}/{loop_count} finish", flush=True)


async def main() -> None:
    args, actions, profile_dir = prepare_runner(load_actions)

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

import asyncio
import json
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from playwright.async_api import async_playwright

from hauntedroom.cv_pattern_matching import (
    DEFAULT_TEMPLATE_THRESHOLD,
    capture_page_grayscale,
    find_template,
    load_template,
    validate_threshold,
)
from hauntedroom.common import (
    ACTION_LOOP_COUNT,
    prepare_runner,
    save_timeout_screenshot,
    start_hotkey_listener,
    start_user_click_logger,
    wait_for_ctrl_c,
    wait_with_countdown,
)
from hauntedroom.custom_macro import run_research_flow


DEFAULT_TEMPLATE_TIMEOUT_MS = 30_000
DEFAULT_TEMPLATE_POLL_MS = 400
DEFAULT_CLICK_DELAY_MS = 400
SUPPORTED_CLICK_POSITIONS = {"bottom_left", "center", "top_middle"}
SKIP_TEMPLATE_MATCHED = object()


def validate_timing_fields(action: dict, index: int) -> None:
    for field in ("timeout_ms", "poll_ms", "delay_ms"):
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

            skip_if_template = action.get("skip_if_template")
            if skip_if_template is not None:
                if not isinstance(skip_if_template, str) or not skip_if_template:
                    raise ValueError(
                        f"Action #{index} skip_if_template must be a template path."
                    )
                skip_if_template_path = (path.parent / skip_if_template).resolve()
                if not skip_if_template_path.is_file():
                    raise ValueError(
                        f"Action #{index} skip_if_template does not exist: "
                        f"{skip_if_template_path}"
                    )
                action["_skip_if_template_path"] = skip_if_template_path

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

            priority = action.get("priority", [])
            if not isinstance(priority, list) or not all(
                isinstance(name, str) for name in priority
            ):
                raise ValueError(f"Action #{index} priority must be an array of names.")
            blocker_paths_by_name = {blocker_path.name: blocker_path for blocker_path in blocker_paths}
            unknown_priority_names = [
                name for name in priority if name not in blocker_paths_by_name
            ]
            if unknown_priority_names:
                raise ValueError(
                    f"Action #{index} priority references unknown blockers: "
                    f"{unknown_priority_names}"
                )
            if len(priority) != len(set(priority)):
                raise ValueError(f"Action #{index} priority contains duplicate names.")
            prioritized_names = priority + [
                blocker_path.name
                for blocker_path in blocker_paths
                if blocker_path.name not in priority
            ]
            blocker_paths = [
                blocker_paths_by_name[name] for name in prioritized_names
            ]

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


async def wait_for_template(
    page,
    template: np.ndarray,
    template_name: str,
    threshold: float,
    timeout_ms: int,
    poll_ms: int,
    stop_event: Optional[asyncio.Event] = None,
    skip_template: Optional[np.ndarray] = None,
    skip_template_name: Optional[str] = None,
) -> object:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_ms / 1000
    best_score = -1.0
    best_skip_score = -1.0

    while True:
        if stop_event is not None and stop_event.is_set():
            return None
        screenshot = await capture_page_grayscale(page)
        center_x, center_y, score = find_template(
            screenshot,
            template,
            template_name,
        )
        best_score = max(best_score, score)

        if score >= threshold:
            return center_x, center_y, score

        if skip_template is not None and skip_template_name is not None:
            _, _, skip_score = find_template(
                screenshot,
                skip_template,
                skip_template_name,
            )
            best_skip_score = max(best_skip_score, skip_score)
            if skip_score >= threshold:
                return SKIP_TEMPLATE_MATCHED

        if loop.time() >= deadline:
            screenshot_path = await save_timeout_screenshot(page, template_name)
            screenshot_suffix = (
                f", screenshot={screenshot_path}" if screenshot_path else ""
            )
            skip_suffix = (
                f", best {skip_template_name} score={best_skip_score:.3f}"
                if skip_template_name is not None
                else ""
            )
            raise TimeoutError(
                f"Timed out waiting for {template_name!r}; "
                f"best score={best_score:.3f}, threshold={threshold:.3f}"
                f"{skip_suffix}{screenshot_suffix}."
            )

        await page.wait_for_timeout(poll_ms)


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
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_ms / 1000
    best_until_score = -1.0

    while True:
        if stop_event is not None and stop_event.is_set():
            return False
        screenshot = await capture_page_grayscale(page)

        blocker_match = None
        for blocker_path in blocker_paths:
            x, y, score = find_template(
                screenshot,
                templates[blocker_path],
                blocker_path.name,
                click_positions.get(blocker_path.name, "center"),
            )
            if score >= threshold:
                blocker_match = (score, blocker_path, x, y)
                break

        if blocker_match:
            score, blocker_path, x, y = blocker_match
            print(
                f"{label}: blocker {blocker_path.name} at {x},{y}, "
                f"score={score:.3f}; click in {delay_ms}ms",
                flush=True,
            )
            await page.wait_for_timeout(delay_ms)
            if stop_event is not None and stop_event.is_set():
                return False
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
            return True

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


async def run_actions(
    page,
    actions: list[dict],
    loop_count: Optional[int] = ACTION_LOOP_COUNT,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    template_paths: set[Path] = set()
    for action in actions:
        if action["type"] == "click_template":
            template_paths.add(action["_template_path"])
            if "_skip_if_template_path" in action:
                template_paths.add(action["_skip_if_template_path"])
        elif action["type"] == "clear_blockers":
            template_paths.update(action["_blocker_paths"])
            template_paths.add(action["_until_template_path"])
    templates = {path: load_template(path) for path in template_paths}
    timeout_count = 0

    loop_index = 0
    while loop_count is None or loop_index < loop_count:
        if stop_event is not None and stop_event.is_set():
            print("Flow stopped; runner is idle.", flush=True)
            return False
        loop_index += 1
        loop_total = "infinite" if loop_count is None else str(loop_count)
        print(f"loop {loop_index}/{loop_total} start", flush=True)
        loop_timed_out = False

        for action_index, action in enumerate(actions, start=1):
            if stop_event is not None and stop_event.is_set():
                print("Flow stopped; runner is idle.", flush=True)
                return False
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
                try:
                    completed = await clear_blockers(
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
                        stop_event,
                    )
                except TimeoutError as error:
                    timeout_count += 1
                    print(
                        f"{label}: timeout count={timeout_count}/2: {error}",
                        flush=True,
                    )
                    if timeout_count >= 2:
                        print("Second timeout; stopping runner.", flush=True)
                        raise
                    print(
                        f"Skipping the rest of loop {loop_index}/{loop_total}; "
                        "retrying from the first action on the next loop.",
                        flush=True,
                    )
                    loop_timed_out = True
                    break
                if not completed:
                    print("Flow stopped; runner is idle.", flush=True)
                    return False
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
                button = action.get("button", "left")
                note = action.get("note")
                note_suffix = f" ({note})" if note else ""
                skip_template_path = action.get("_skip_if_template_path")

                print(
                    f"{loop_index}.{action_index}: wait for "
                    f"{template_path.name}{note_suffix}",
                    flush=True,
                )
                try:
                    match = await wait_for_template(
                        page,
                        templates[template_path],
                        template_path.name,
                        threshold,
                        timeout_ms,
                        poll_ms,
                        stop_event,
                        templates[skip_template_path] if skip_template_path else None,
                        skip_template_path.name if skip_template_path else None,
                    )
                except TimeoutError as error:
                    timeout_count += 1
                    print(
                        f"{loop_index}.{action_index}{note_suffix}: "
                        f"timeout count={timeout_count}/2: {error}",
                        flush=True,
                    )
                    if timeout_count >= 2:
                        print("Second timeout; stopping runner.", flush=True)
                        raise
                    print(
                        f"Skipping the rest of loop {loop_index}/{loop_total}; "
                        "retrying from the first action on the next loop.",
                        flush=True,
                    )
                    loop_timed_out = True
                    break
                if match is SKIP_TEMPLATE_MATCHED:
                    print(
                        f"{loop_index}.{action_index}: skip {template_path.name}; "
                        f"{skip_template_path.name} already ready",
                        flush=True,
                    )
                    continue
                if match is None:
                    print("Flow stopped; runner is idle.", flush=True)
                    return False
                x, y, score = match
                print(
                    f"{loop_index}.{action_index}: detected "
                    f"{template_path.name} at {x},{y}, score={score:.3f}; "
                    f"click {click_count} time(s), wait {delay_ms}ms before each",
                    flush=True,
                )
                for _ in range(click_count):
                    await page.wait_for_timeout(delay_ms)
                    if stop_event is not None and stop_event.is_set():
                        print("Flow stopped; runner is idle.", flush=True)
                        return False
                    await page.evaluate(
                        "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
                    )
                    await page.mouse.click(x, y, button=button)
                continue

            ms = int(action["ms"])
            note = action.get("note")
            note_suffix = f" ({note})" if note else ""
            completed = await wait_with_countdown(
                page,
                ms,
                f"{loop_index}.{action_index}{note_suffix}",
                stop_event,
            )
            if not completed:
                print("Flow stopped; runner is idle.", flush=True)
                return False

        if loop_timed_out:
            continue

        if timeout_count:
            print(
                f"loop {loop_index}/{loop_total} completed successfully; "
                "resetting timeout count to 0.",
                flush=True,
            )
            timeout_count = 0

        print(f"loop {loop_index}/{loop_total} finish", flush=True)

    return True


async def run_standby_controller(page, actions: list[dict]) -> None:
    command_queue: asyncio.Queue[str] = asyncio.Queue()
    await start_hotkey_listener(page, command_queue)

    flow_task = None
    stop_event = None
    command_names = {"1": "enter-exit room", "9": "research"}
    print(
        "Runner idle. Shift+1: enter-exit room; Shift+9: research; "
        "Shift+0: stop current flow; Ctrl+C in terminal: close runner.",
        flush=True,
    )

    command_task = asyncio.create_task(command_queue.get())
    try:
        while True:
            wait_for = {command_task}
            if flow_task is not None:
                wait_for.add(flow_task)

            done, _ = await asyncio.wait(wait_for, return_when=asyncio.FIRST_COMPLETED)

            if flow_task is not None and flow_task in done:
                try:
                    flow_task.result()
                except Exception as error:
                    print(f"Flow failed; runner is idle: {error}", flush=True)
                flow_task = None
                stop_event = None
                print("Runner idle.", flush=True)

            if command_task not in done:
                continue

            command = command_task.result()
            command_task = asyncio.create_task(command_queue.get())
            if command == "0":
                if flow_task is None:
                    print("Runner is already idle.", flush=True)
                else:
                    print("Stopping current flow...", flush=True)
                    stop_event.set()
                continue

            if command not in command_names:
                print(f"Shift+{command}: no flow configured.", flush=True)
                continue

            if flow_task is not None:
                print(
                    f"Runner busy; press Shift+0 before starting Shift+{command}.",
                    flush=True,
                )
                continue

            stop_event = asyncio.Event()
            print(f"Starting {command_names[command]} flow...", flush=True)
            if command == "1":
                flow_task = asyncio.create_task(
                    run_actions(page, actions, loop_count=None, stop_event=stop_event)
                )
            else:
                flow_task = asyncio.create_task(run_research_flow(page, stop_event))
    finally:
        command_task.cancel()
        await asyncio.gather(command_task, return_exceptions=True)
        if flow_task is not None:
            stop_event.set()
            await asyncio.gather(flow_task, return_exceptions=True)


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
                await run_standby_controller(page, actions)
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

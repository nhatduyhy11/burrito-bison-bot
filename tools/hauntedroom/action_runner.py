import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.clear_blocker import clear_blockers
from hauntedroom.common import (
    ACTION_LOOP_COUNT,
    save_timeout_screenshot,
    wait_with_countdown,
)
from hauntedroom.cv_pattern_matching import (
    DEFAULT_TEMPLATE_THRESHOLD,
    capture_page_grayscale,
    find_template,
    load_template,
)


DEFAULT_TEMPLATE_TIMEOUT_MS = 30_000
DEFAULT_TEMPLATE_POLL_MS = 400
DEFAULT_CLICK_DELAY_MS = 400
SKIP_TEMPLATE_MATCHED = object()


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
                await page.evaluate(
                    "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
                )
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

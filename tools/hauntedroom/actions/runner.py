import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.actions.models import (
    Action,
    ClearBlockersAction,
    ClickAction,
    ClickTemplateAction,
    WaitAction,
)
from hauntedroom.control_events.blockers import clear_blockers
from hauntedroom.core.mouse import bot_click
from hauntedroom.core.runtime import (
    ACTION_LOOP_COUNT,
    flow_checkpoint,
    flow_time,
    save_timeout_screenshot,
    wait_for_flow_timeout,
    wait_with_countdown,
)
from hauntedroom.core.template import (
    TEMPLATE_SCALES,
    Region,
    find_template,
    load_template,
)
from hauntedroom.core.vision import capture_page_grayscale


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
    click_position: str = "center",
    template_scales: tuple[float, ...] = TEMPLATE_SCALES,
    skip_template_scales: tuple[float, ...] = TEMPLATE_SCALES,
    region: Optional[Region] = None,
) -> object:
    deadline = flow_time(stop_event) + timeout_ms / 1000
    best_score = -1.0
    best_skip_score = -1.0

    while True:
        if not await flow_checkpoint(stop_event):
            return None
        screenshot = await capture_page_grayscale(page)
        center_x, center_y, score = find_template(
            screenshot,
            template,
            template_name,
            click_position,
            scales=template_scales,
            region=region,
        )
        best_score = max(best_score, score)

        if score >= threshold:
            return center_x, center_y, score

        if skip_template is not None and skip_template_name is not None:
            _, _, skip_score = find_template(
                screenshot,
                skip_template,
                skip_template_name,
                scales=skip_template_scales,
            )
            best_skip_score = max(best_skip_score, skip_score)
            if skip_score >= threshold:
                return SKIP_TEMPLATE_MATCHED

        if flow_time(stop_event) >= deadline:
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

        if not await wait_for_flow_timeout(page, poll_ms, stop_event):
            return None


def note_suffix(note: Optional[str]) -> str:
    return f" ({note})" if note else ""


def action_label(loop_index: int, action_index: int, note: Optional[str]) -> str:
    return f"{loop_index}.{action_index}{note_suffix(note)}"


def collect_template_paths(actions: list[Action]) -> set[Path]:
    template_paths: set[Path] = set()
    for action in actions:
        if isinstance(action, ClickTemplateAction):
            template_paths.add(action.template_path)
            if action.skip_if_template_path is not None:
                template_paths.add(action.skip_if_template_path)
        elif isinstance(action, ClearBlockersAction):
            template_paths.update(action.blocker_paths)
            template_paths.add(action.until_template_path)
    return template_paths


async def execute_click_action(page, action: ClickAction, label: str) -> bool:
    print(f"{label}: click {action.x},{action.y}", flush=True)
    await bot_click(page, (action.x, action.y), button=action.button)
    return True


async def execute_clear_blockers_action(
    page,
    action: ClearBlockersAction,
    templates: dict[Path, np.ndarray],
    label: str,
    stop_event: Optional[asyncio.Event],
) -> bool:
    return await clear_blockers(
        page,
        action.blocker_paths,
        action.until_template_path,
        templates,
        action.threshold,
        action.timeout_ms,
        action.poll_ms,
        action.delay_ms,
        action.click_positions,
        label,
        stop_event,
        action.until_template_scales,
    )


async def execute_click_template_action(
    page,
    action: ClickTemplateAction,
    templates: dict[Path, np.ndarray],
    loop_index: int,
    action_index: int,
    stop_event: Optional[asyncio.Event],
) -> bool:
    template_path = action.template_path
    skip_template_path = action.skip_if_template_path
    repeat_delay_ms = action.effective_repeat_delay_ms

    print(
        f"{loop_index}.{action_index}: wait for "
        f"{template_path.name}{note_suffix(action.note)}",
        flush=True,
    )
    match = await wait_for_template(
        page,
        templates[template_path],
        template_path.name,
        action.threshold,
        action.timeout_ms,
        action.poll_ms,
        stop_event=stop_event,
        skip_template=(
            templates[skip_template_path] if skip_template_path is not None else None
        ),
        skip_template_name=(
            skip_template_path.name if skip_template_path is not None else None
        ),
        click_position=action.click_position,
        template_scales=action.template_scales,
        skip_template_scales=action.skip_template_scales,
        region=action.region,
    )
    if match is SKIP_TEMPLATE_MATCHED:
        skip_template_name = (
            skip_template_path.name
            if skip_template_path is not None
            else "skip template"
        )
        print(
            f"{loop_index}.{action_index}: skip {template_path.name}; "
            f"{skip_template_name} already ready",
            flush=True,
        )
        return True
    if match is None:
        return False

    x, y, score = match
    repeat_summary = (
        f"; up to {action.click_count - 1} repeat(s), recheck after "
        f"{repeat_delay_ms}ms"
        if action.recheck_before_repeat and action.click_count > 1
        else f"; click {action.click_count} time(s)"
    )
    print(
        f"{loop_index}.{action_index}: detected "
        f"{template_path.name} at {x},{y}, score={score:.3f}; "
        f"first click after {action.delay_ms}ms{repeat_summary}",
        flush=True,
    )

    for click_index in range(action.click_count):
        wait_ms = action.delay_ms if click_index == 0 else repeat_delay_ms
        if not await wait_for_flow_timeout(page, wait_ms, stop_event):
            return False

        if click_index > 0 and action.recheck_before_repeat:
            screenshot = await capture_page_grayscale(page)
            x, y, score = find_template(
                screenshot,
                templates[template_path],
                template_path.name,
                action.click_position,
                scales=action.template_scales,
                region=action.region,
            )
            if score < action.threshold:
                print(
                    f"{loop_index}.{action_index}: "
                    f"{template_path.name} disappeared after "
                    f"{click_index} click(s), score={score:.3f}; "
                    "skip remaining repeat clicks",
                    flush=True,
                )
                break
            print(
                f"{loop_index}.{action_index}: "
                f"{template_path.name} still present at {x},{y}, "
                f"score={score:.3f}; repeat click",
                flush=True,
            )

        await bot_click(page, (x, y), button=action.button)

    return True


async def execute_wait_action(
    page,
    action: WaitAction,
    label: str,
    stop_event: Optional[asyncio.Event],
) -> bool:
    return await wait_with_countdown(page, action.ms, label, stop_event)


async def execute_action(
    page,
    action: Action,
    templates: dict[Path, np.ndarray],
    loop_index: int,
    action_index: int,
    stop_event: Optional[asyncio.Event],
) -> bool:
    label = action_label(loop_index, action_index, action.note)
    if isinstance(action, ClickAction):
        return await execute_click_action(page, action, label)
    if isinstance(action, ClearBlockersAction):
        return await execute_clear_blockers_action(
            page,
            action,
            templates,
            label,
            stop_event,
        )
    if isinstance(action, ClickTemplateAction):
        return await execute_click_template_action(
            page,
            action,
            templates,
            loop_index,
            action_index,
            stop_event,
        )
    if isinstance(action, WaitAction):
        return await execute_wait_action(page, action, label, stop_event)

    raise TypeError(f"Unsupported action object: {action!r}")


def log_action_timeout(
    error: TimeoutError,
    loop_index: int,
    loop_total: str,
    label: str,
    timeout_count: int,
    loop_count: Optional[int],
) -> bool:
    print(
        f"{label}: timeout count={timeout_count}/2: {error}",
        flush=True,
    )
    if timeout_count >= 2:
        print("Second timeout; stopping runner.", flush=True)
        raise error
    if loop_count is not None and loop_index >= loop_count:
        print(
            "Skipping the rest of the final action attempt; "
            "no retry remains.",
            flush=True,
        )
    else:
        print(
            "Skipping the rest of action loop "
            f"{loop_index}/{loop_total}; retrying from the "
            "first action on the next loop.",
            flush=True,
        )
    return True


async def run_actions(
    page,
    actions: list[Action],
    loop_count: Optional[int] = ACTION_LOOP_COUNT,
    stop_event: Optional[asyncio.Event] = None,
    stop_after_success: bool = False,
) -> bool:
    template_paths = collect_template_paths(actions)
    templates = {path: load_template(path) for path in template_paths}
    timeout_count = 0

    loop_index = 0
    while loop_count is None or loop_index < loop_count:
        if not await flow_checkpoint(stop_event):
            print("Flow stopped; runner is idle.", flush=True)
            return False
        loop_index += 1
        loop_total = "infinite" if loop_count is None else str(loop_count)
        print(f"Action loop {loop_index}/{loop_total} start", flush=True)
        loop_timed_out = False

        for action_index, action in enumerate(actions, start=1):
            if not await flow_checkpoint(stop_event):
                print("Flow stopped; runner is idle.", flush=True)
                return False

            label = action_label(loop_index, action_index, action.note)
            try:
                completed = await execute_action(
                    page,
                    action,
                    templates,
                    loop_index,
                    action_index,
                    stop_event,
                )
            except TimeoutError as error:
                timeout_count += 1
                loop_timed_out = log_action_timeout(
                    error,
                    loop_index,
                    loop_total,
                    label,
                    timeout_count,
                    loop_count,
                )
                break
            if not completed:
                print("Flow stopped; runner is idle.", flush=True)
                return False

        if loop_timed_out:
            if loop_count is not None and loop_index >= loop_count:
                print(
                    f"Action loop {loop_index}/{loop_total} exhausted after "
                    "a timeout; returning failure.",
                    flush=True,
                )
                return False
            continue

        if timeout_count:
            print(
                f"Action loop {loop_index}/{loop_total} completed successfully; "
                "resetting timeout count to 0.",
                flush=True,
            )
            timeout_count = 0

        print(f"Action loop {loop_index}/{loop_total} finish", flush=True)
        if stop_after_success:
            return True

    return True

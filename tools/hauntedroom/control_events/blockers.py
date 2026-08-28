import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.control_events.new_tab_blocker import close_profile_popup_tabs
from hauntedroom.core.mouse import click_and_wait
from hauntedroom.core.runtime import (
    flow_checkpoint,
    flow_time,
    save_timeout_screenshot,
    wait_for_flow_timeout,
)
from hauntedroom.core.template_matching import (
    TEMPLATE_SCALES,
    ClickPosition,
    find_template,
)
from hauntedroom.core.vision import capture_page_grayscale


NEWBIE_BLOCKER_TEMPLATE_NAME = "overlay_newbie.png"
NEWBIE_BLOCKER_DISMISS_CLICK = (124, 98)


def blocker_dismiss_click(
    template_name: str,
    detected_x: int,
    detected_y: int,
) -> tuple[int, int]:
    """Return the actual dismiss target for a detected blocker."""
    if template_name == NEWBIE_BLOCKER_TEMPLATE_NAME:
        return NEWBIE_BLOCKER_DISMISS_CLICK
    return detected_x, detected_y


async def clear_blockers(
    page,
    blocker_paths: list[Path],
    until_template_path: Path,
    templates: dict[Path, np.ndarray],
    threshold: float,
    timeout_ms: int,
    poll_ms: int,
    delay_ms: int,
    click_positions: dict[str, ClickPosition],
    label: str,
    stop_event: Optional[asyncio.Event] = None,
    until_template_scales: tuple[float, ...] = TEMPLATE_SCALES,
) -> bool:
    deadline = flow_time(stop_event) + timeout_ms / 1000
    best_until_score = -1.0

    while True:
        if not await flow_checkpoint(stop_event):
            return False
        await close_profile_popup_tabs(page, label)
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
                x, y = blocker_dismiss_click(blocker_path.name, x, y)
                blocker_match = (score, blocker_path, x, y)
                break

        if blocker_match:
            score, blocker_path, x, y = blocker_match
            print(
                f"{label}: blocker {blocker_path.name} at {x},{y}, "
                f"score={score:.3f}; click in {delay_ms}ms",
                flush=True,
            )
            if not await wait_for_flow_timeout(page, delay_ms, stop_event):
                return False
            if not await click_and_wait(
                page, (x, y), poll_ms, stop_event
            ):
                return False
            deadline = flow_time(stop_event) + timeout_ms / 1000
            continue

        _, _, until_score = find_template(
            screenshot,
            templates[until_template_path],
            until_template_path.name,
            scales=until_template_scales,
        )
        best_until_score = max(best_until_score, until_score)
        if until_score >= threshold:
            print(
                f"{label}: no blocker; {until_template_path.name} ready "
                f"(score={until_score:.3f})",
                flush=True,
            )
            return True

        if flow_time(stop_event) >= deadline:
            screenshot_path = await save_timeout_screenshot(page, label)
            screenshot_suffix = (
                f", screenshot={screenshot_path}" if screenshot_path else ""
            )
            raise TimeoutError(
                f"{label}: timed out clearing blockers and waiting for "
                f"{until_template_path.name!r}; best score={best_until_score:.3f}, "
                f"threshold={threshold:.3f}{screenshot_suffix}."
            )

        if not await wait_for_flow_timeout(page, poll_ms, stop_event):
            return False

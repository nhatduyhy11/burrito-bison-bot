import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.core.runtime import save_timeout_screenshot
from hauntedroom.core.vision import (
    TEMPLATE_SCALES,
    capture_page_grayscale,
    find_template,
)


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
    until_template_scales: tuple[float, ...] = TEMPLATE_SCALES,
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

"""Lobby_map wrapper for the shared hero-select phase.

The click_hero_select_battle action keeps lobby_map's recovery loop (popup
tabs, blockers, re-clicking the HOME entry after an interrupted transition);
detection delegates to the shared hauntedroom.flows.hero_select package.
"""

import asyncio
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.control_events.new_tab_blocker import close_profile_popup_tabs
from hauntedroom.core.mouse import bot_click, click_and_wait
from hauntedroom.core.runtime import (
    flow_checkpoint,
    flow_time,
    save_timeout_screenshot,
    wait_for_flow_timeout,
)
from hauntedroom.core.template_matching import (
    ClickPosition,
    find_template,
    resolve_blocker_click,
)
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.hero_select import find_battle_button


async def click_hero_select_battle(
    page,
    blocker_paths: tuple[Path, ...],
    header_template_path: Path,
    entry_template_path: Path,
    templates: dict[Path, np.ndarray],
    threshold: float,
    timeout_ms: int,
    poll_ms: int,
    delay_ms: int,
    click_positions: dict[str, ClickPosition],
    entry_click_position: ClickPosition,
    entry_template_scales: tuple[float, ...],
    label: str,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    """Clear overlays, confirm hero-select, then click its yellow button."""
    deadline = flow_time(stop_event) + timeout_ms / 1000

    while True:
        if not await flow_checkpoint(stop_event):
            return False
        await close_profile_popup_tabs(page, label)
        screenshot = await capture_page_bgr(page)
        screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

        blocker_match = None
        for blocker_path in blocker_paths:
            x, y, score = find_template(
                screenshot_gray,
                templates[blocker_path],
                blocker_path.name,
                click_positions.get(blocker_path.name, "center"),
            )
            if score >= threshold:
                blocker_match = (
                    score,
                    blocker_path,
                    *resolve_blocker_click(blocker_path.name, x, y),
                )
                break

        if blocker_match is not None:
            score, blocker_path, x, y = blocker_match
            print(
                f"{label}: blocker {blocker_path.name} at {x},{y}, "
                f"score={score:.3f}; click in {delay_ms}ms",
                flush=True,
            )
            if not await wait_for_flow_timeout(page, delay_ms, stop_event):
                return False
            if not await click_and_wait(page, (x, y), poll_ms, stop_event):
                return False
            deadline = flow_time(stop_event) + timeout_ms / 1000
            continue

        button = find_battle_button(
            screenshot,
            templates[header_template_path],
        )
        if button is not None:
            x, y = button.center
            print(
                f"{label}: hero-select screen ready; yellow battle button "
                f"at {x},{y}; click in {delay_ms}ms",
                flush=True,
            )
            if not await wait_for_flow_timeout(page, delay_ms, stop_event):
                return False
            await bot_click(page, (x, y))
            return True

        # A blocker can hide the HOME entry immediately after it is clicked.
        # Once the blocker closes, the game may return to that same entry
        # screen instead of advancing to hero-select. Retry the interrupted
        # transition rather than waiting forever for the destination screen.
        entry_x, entry_y, entry_score = find_template(
            screenshot_gray,
            templates[entry_template_path],
            entry_template_path.name,
            entry_click_position,
            scales=entry_template_scales,
        )
        if entry_score >= threshold:
            print(
                f"{label}: {entry_template_path.name} returned after an "
                f"interruption at {entry_x},{entry_y}, "
                f"score={entry_score:.3f}; retry click in {delay_ms}ms",
                flush=True,
            )
            if not await wait_for_flow_timeout(page, delay_ms, stop_event):
                return False
            if not await click_and_wait(
                page,
                (entry_x, entry_y),
                poll_ms,
                stop_event,
            ):
                return False
            deadline = flow_time(stop_event) + timeout_ms / 1000
            continue

        if flow_time(stop_event) >= deadline:
            screenshot_path = await save_timeout_screenshot(page, label)
            screenshot_suffix = (
                f", screenshot={screenshot_path}" if screenshot_path else ""
            )
            raise TimeoutError(
                f"{label}: timed out waiting for the hero-select header and "
                f"yellow battle button{screenshot_suffix}."
            )

        if not await wait_for_flow_timeout(page, poll_ms, stop_event):
            return False

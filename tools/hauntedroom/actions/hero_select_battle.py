"""Language-agnostic hero-select screen and battle-button detection."""

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
from hauntedroom.core.template_matching import ClickPosition, find_template
from hauntedroom.core.vision import (
    ColorComponentMatch,
    capture_page_bgr,
)
from hauntedroom.vision.buttons import ButtonGeometry, find_colored_button


# The title text changes by locale. Match only the text-free left corner of
# its backing plate, restricted to the fixed top-screen neighborhood.
HERO_SELECT_HEADER_REGION = (210, 10, 430, 90)
HERO_SELECT_HEADER_THRESHOLD = 0.80
BATTLE_START_BUTTON_REGION = (230, 650, 410, 719)
BATTLE_START_BUTTON_GEOMETRY = ButtonGeometry(
    min_area=2_400,
    min_width=95,
    max_width=130,
    min_height=28,
    max_height=45,
    min_fill_ratio=0.65,
)


def find_hero_select_battle_button(
    image: np.ndarray,
    header_template: np.ndarray,
) -> Optional[ColorComponentMatch]:
    """Return the yellow start button only on the hero-select screen."""
    if image.ndim != 3 or image.shape[2] != 3:
        return None
    screenshot_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, _, header_score = find_template(
        screenshot_gray,
        header_template,
        "hero_select_battle_banner_left.png",
        scales=(1.0,),
        region=HERO_SELECT_HEADER_REGION,
    )
    if header_score < HERO_SELECT_HEADER_THRESHOLD:
        return None
    return find_colored_button(
        image,
        BATTLE_START_BUTTON_REGION,
        "yellow",
        BATTLE_START_BUTTON_GEOMETRY,
    )


async def click_hero_select_battle(
    page,
    blocker_paths: tuple[Path, ...],
    header_template_path: Path,
    templates: dict[Path, np.ndarray],
    threshold: float,
    timeout_ms: int,
    poll_ms: int,
    delay_ms: int,
    click_positions: dict[str, ClickPosition],
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
                blocker_match = (score, blocker_path, x, y)
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

        button = find_hero_select_battle_button(
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

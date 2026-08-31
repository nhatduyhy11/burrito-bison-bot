"""Language-agnostic detection for the pause popup's exit controls."""

import asyncio
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.mouse import bot_click
from hauntedroom.core.runtime import (
    flow_checkpoint,
    flow_time,
    save_timeout_screenshot,
    wait_for_flow_timeout,
)
from hauntedroom.core.template_matching import find_template
from hauntedroom.core.vision import (
    ColorComponentMatch,
    capture_page_bgr,
)
from hauntedroom.vision.buttons import ButtonGeometry, find_colored_button


PAUSE_EXIT_RED_REGION = (180, 600, 325, 665)
PAUSE_EXIT_RED_GEOMETRY = ButtonGeometry(
    min_area=2_000,
    min_width=100,
    max_width=120,
    min_height=30,
    max_height=38,
    min_fill_ratio=0.60,
)
PAUSE_EXIT_YELLOW_REGION = (320, 600, 465, 665)
PAUSE_EXIT_YELLOW_GEOMETRY = ButtonGeometry(
    min_area=2_000,
    min_width=100,
    max_width=120,
    min_height=30,
    max_height=38,
    min_fill_ratio=0.60,
)
MIN_BUTTON_GAP = 20
MAX_BUTTON_GAP = 50
MAX_BUTTON_Y_DELTA = 3
MAX_BUTTON_HEIGHT_DELTA = 4

# Stop above the underlying game button. Only a few pixels of that lower
# button can enter this ROI, so it cannot satisfy the complete-component
# geometry required below.
MAP_EXIT_BACK_REGION = (245, 550, 390, 658)
MAP_EXIT_BACK_GEOMETRY = ButtonGeometry(
    min_area=2_500,
    min_width=100,
    max_width=120,
    min_height=30,
    max_height=40,
    min_fill_ratio=0.65,
)
MIN_MAP_EXIT_BACK_X = 258
MAX_MAP_EXIT_BACK_X = 270
MIN_MAP_EXIT_BACK_Y = 550
MAX_MAP_EXIT_BACK_Y = 625


def find_pause_exit_button(
    image: np.ndarray,
) -> Optional[ColorComponentMatch]:
    """Return red exit only when its adjacent yellow button also matches."""
    red = find_colored_button(
        image,
        PAUSE_EXIT_RED_REGION,
        "red",
        PAUSE_EXIT_RED_GEOMETRY,
    )
    yellow = find_colored_button(
        image,
        PAUSE_EXIT_YELLOW_REGION,
        "yellow",
        PAUSE_EXIT_YELLOW_GEOMETRY,
    )
    if red is None or yellow is None:
        return None

    gap = yellow.x - (red.x + red.width)
    if (
        not MIN_BUTTON_GAP <= gap <= MAX_BUTTON_GAP
        or abs(red.y - yellow.y) > MAX_BUTTON_Y_DELTA
        or abs(red.height - yellow.height) > MAX_BUTTON_HEIGHT_DELTA
    ):
        return None
    return red


def find_map_exit_back_button(
    image: np.ndarray,
) -> Optional[ColorComponentMatch]:
    """Find the complete popup button without accepting the button below it."""
    button = find_colored_button(
        image,
        MAP_EXIT_BACK_REGION,
        "yellow",
        MAP_EXIT_BACK_GEOMETRY,
    )
    if button is None:
        return None
    if (
        not MIN_MAP_EXIT_BACK_X <= button.x <= MAX_MAP_EXIT_BACK_X
        or not MIN_MAP_EXIT_BACK_Y <= button.y <= MAX_MAP_EXIT_BACK_Y
    ):
        return None
    return button


async def click_pause_exit(
    page,
    retry_template: Optional[np.ndarray],
    retry_template_name: Optional[str],
    retry_template_threshold: float,
    retry_template_scales: tuple[float, ...],
    retry_template_region: Optional[tuple[int, int, int, int]],
    timeout_ms: int,
    poll_ms: int,
    delay_ms: int,
    label: str,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    """Wait for pause controls, retrying the pause trigger until they appear."""
    deadline = flow_time(stop_event) + timeout_ms / 1000

    while True:
        if not await flow_checkpoint(stop_event):
            return False
        screenshot = await capture_page_bgr(page)
        button = find_pause_exit_button(screenshot)
        if button is not None:
            x, y = button.center
            print(
                f"{label}: pause exit button pair ready; red button at "
                f"{x},{y}; click in {delay_ms}ms",
                flush=True,
            )
            if not await wait_for_flow_timeout(page, delay_ms, stop_event):
                return False
            await bot_click(page, (x, y))
            return True

        # The first click can be consumed while the game is still settling.
        # When that happens, retry only the verified pause icon, never an
        # arbitrary fixed coordinate, until the paired pause controls appear.
        if retry_template is not None and retry_template_name is not None:
            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            x, y, score = find_template(
                screenshot_gray,
                retry_template,
                retry_template_name,
                scales=retry_template_scales,
                region=retry_template_region,
            )
            if score >= retry_template_threshold:
                print(
                    f"{label}: pause controls not visible; retry "
                    f"{retry_template_name} at {x},{y}, score={score:.3f}",
                    flush=True,
                )
                await bot_click(page, (x, y))
                if not await wait_for_flow_timeout(page, delay_ms, stop_event):
                    return False
                continue

        if flow_time(stop_event) >= deadline:
            screenshot_path = await save_timeout_screenshot(page, label)
            screenshot_suffix = (
                f", screenshot={screenshot_path}" if screenshot_path else ""
            )
            raise TimeoutError(
                f"{label}: timed out waiting for the paired red and yellow "
                f"pause buttons{screenshot_suffix}."
            )

        if not await wait_for_flow_timeout(page, poll_ms, stop_event):
            return False


async def click_map_exit_back(
    page,
    skip_if_template_path: Optional[Path],
    templates: dict[Path, np.ndarray],
    threshold: float,
    timeout_ms: int,
    poll_ms: int,
    delay_ms: int,
    label: str,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    """Click the popup's yellow back button, or skip if HOME is ready."""
    deadline = flow_time(stop_event) + timeout_ms / 1000

    while True:
        if not await flow_checkpoint(stop_event):
            return False
        screenshot = await capture_page_bgr(page)
        button = find_map_exit_back_button(screenshot)
        if button is not None:
            x, y = button.center
            print(
                f"{label}: post-exit yellow button ready at {x},{y}; "
                f"click in {delay_ms}ms",
                flush=True,
            )
            if not await wait_for_flow_timeout(page, delay_ms, stop_event):
                return False
            await bot_click(page, (x, y))
            return True

        if skip_if_template_path is not None:
            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            _, _, skip_score = find_template(
                screenshot_gray,
                templates[skip_if_template_path],
                skip_if_template_path.name,
                scales=(1.0,),
            )
            if skip_score >= threshold:
                print(
                    f"{label}: skip post-exit button; "
                    f"{skip_if_template_path.name} already ready",
                    flush=True,
                )
                return True

        if flow_time(stop_event) >= deadline:
            screenshot_path = await save_timeout_screenshot(page, label)
            screenshot_suffix = (
                f", screenshot={screenshot_path}" if screenshot_path else ""
            )
            raise TimeoutError(
                f"{label}: timed out waiting for the complete centered yellow "
                f"post-exit button{screenshot_suffix}."
            )

        if not await wait_for_flow_timeout(page, poll_ms, stop_event):
            return False

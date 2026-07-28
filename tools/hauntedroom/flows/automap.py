import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Optional

import cv2
import numpy as np

from hauntedroom.core.runtime import wait_with_countdown
from hauntedroom.core.vision import (
    capture_page_bgr,
    find_template,
    find_template_matches,
    load_template,
)


AUTOMAP_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "rooms" / "automap"
ROOM_TEMPLATE_DIR = AUTOMAP_TEMPLATE_DIR.parent
LV_UP_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "lv_up.png"
BUILT_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "built.png"
LV_SPIN_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "lv_spin.png"
MAP_END_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "map_end.png"
WIN_REWARD_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "win_reward.png"
START_HOME_TEMPLATE_PATH = ROOM_TEMPLATE_DIR / "start_home.png"
# lv_up.png excludes the two-pixel background border. The two valid icons in
# the captured battle UI score about 0.95 and 0.86; other UI stays below 0.60.
AUTOMAP_TEMPLATE_THRESHOLD = 0.80
BUILT_TEMPLATE_THRESHOLD = 0.80
AUTOMAP_POLL_MS = 600
AUTOMAP_ACTION_DELAY_MS = 800
LV_SPIN_CLICK_OFFSET_X = -70
LV_SPIN_TEMPLATE_THRESHOLD = 0.58
LV_SPIN_TEMPLATE_SCALES = (1.0, 0.8, 0.67)
LV_SPIN_SEARCH_TOP_RATIO = 0.75
MAP_END_TEMPLATE_THRESHOLD = 0.90
MAP_END_CHECK_INTERVAL_SEC = 5.0
WIN_REWARD_TEMPLATE_THRESHOLD = 0.90
START_HOME_TEMPLATE_THRESHOLD = 0.90

# The right-aligned price digit is more stable than the money icon or the
# complete price. Coordinates are in the fixed 640x720 Playwright viewport.
PROTECT_AVAILABLE_REGION = (328, 630, 348, 647)
PROTECT_CLICK = (320, 640)
PROTECT_CONFIRM_CLICK = (357, 623)
UPGRADE_CONFIRM_CLICK = (430, 366)

# A popup can contain one or two choices, and the single choice is vertically
# centered. Detect the yellow buttons instead of assuming fixed row positions.
BUILD_BUTTON_SEARCH_REGION = (380, 300, 480, 450)
BUILD_BUTTON_MIN_HUE = 15
BUILD_BUTTON_MAX_HUE = 40
BUILD_BUTTON_MIN_SATURATION = 100
BUILD_BUTTON_MIN_VALUE = 180
BUILD_BUTTON_MIN_AREA = 500
BUILD_BUTTON_MIN_WIDTH = 50
BUILD_BUTTON_MIN_HEIGHT = 15

WHITE_MAX_SATURATION = 50
WHITE_MIN_VALUE = 180
WHITE_MIN_PIXELS = 8

SituationHandler = Callable[[np.ndarray, np.ndarray], Awaitable[bool]]


def region_has_enough_white(
    image: np.ndarray,
    region: tuple[int, int, int, int] = PROTECT_AVAILABLE_REGION,
    min_pixels: int = WHITE_MIN_PIXELS,
) -> bool:
    """Return True only when the configured price region is visibly white."""
    x1, y1, x2, y2 = region
    height, width = image.shape[:2]
    if (
        x1 < 0
        or y1 < 0
        or x2 > width
        or y2 > height
        or x1 >= x2
        or y1 >= y2
    ):
        return False

    hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    _hue, saturation, value = np.moveaxis(hsv, -1, 0)
    white_pixels = (
        (saturation <= WHITE_MAX_SATURATION)
        & (value >= WHITE_MIN_VALUE)
    )
    return int(np.count_nonzero(white_pixels)) >= min_pixels


def find_first_available_build_option(
    image: np.ndarray,
) -> Optional[tuple[int, int]]:
    """Return the first top-to-bottom yellow button with a white price."""
    x1, y1, x2, y2 = BUILD_BUTTON_SEARCH_REGION
    height, width = image.shape[:2]
    if x2 > width or y2 > height:
        return None

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    search = hsv[y1:y2, x1:x2]
    yellow_mask = (
        (search[:, :, 0] >= BUILD_BUTTON_MIN_HUE)
        & (search[:, :, 0] <= BUILD_BUTTON_MAX_HUE)
        & (search[:, :, 1] >= BUILD_BUTTON_MIN_SATURATION)
        & (search[:, :, 2] >= BUILD_BUTTON_MIN_VALUE)
    ).astype(np.uint8)
    component_count, _labels, stats, _centroids = (
        cv2.connectedComponentsWithStats(yellow_mask)
    )

    buttons: list[tuple[int, int, int, int]] = []
    for component in range(1, component_count):
        local_x, local_y, button_width, button_height, area = stats[component]
        if (
            area < BUILD_BUTTON_MIN_AREA
            or button_width < BUILD_BUTTON_MIN_WIDTH
            or button_height < BUILD_BUTTON_MIN_HEIGHT
        ):
            continue
        buttons.append(
            (
                x1 + int(local_x),
                y1 + int(local_y),
                int(button_width),
                int(button_height),
            )
        )

    for button_x, button_y, button_width, button_height in sorted(
        buttons,
        key=lambda button: button[1],
    ):
        # Prices are in the right half; excluding the resource icon prevents
        # white pixels in that icon from making a red price look available.
        price_region = (
            button_x + button_width // 2,
            button_y,
            button_x + button_width,
            button_y + button_height,
        )
        if region_has_enough_white(image, price_region):
            return (
                button_x + button_width // 2,
                button_y + button_height // 2,
            )

    return None


async def _click(page, x: int, y: int) -> None:
    await page.evaluate(
        "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
    )
    await page.mouse.click(x, y)


async def run_automap_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
    lv_up_template_path: Path = LV_UP_TEMPLATE_PATH,
    threshold: float = AUTOMAP_TEMPLATE_THRESHOLD,
    built_template_path: Path = BUILT_TEMPLATE_PATH,
    lv_spin_template_path: Path = LV_SPIN_TEMPLATE_PATH,
    map_end_template_path: Path = MAP_END_TEMPLATE_PATH,
    win_reward_template_path: Path = WIN_REWARD_TEMPLATE_PATH,
    start_home_template_path: Path = START_HOME_TEMPLATE_PATH,
) -> bool:
    """Run battle situations in priority order until stopped.

    A handler returns True after acting. The loop then starts again at the first
    handler, which lets a higher-priority situation preempt lower priorities.
    New battle situations can be appended to ``handlers`` without changing the
    scheduling loop.
    """
    lv_up_template = load_template(lv_up_template_path)
    built_template = load_template(built_template_path)
    lv_spin_template = load_template(lv_spin_template_path)
    map_end_template = load_template(map_end_template_path)
    win_reward_template = load_template(win_reward_template_path)
    start_home_template = load_template(start_home_template_path)
    loop = asyncio.get_running_loop()
    last_map_end_check: Optional[float] = None
    map_completed = False

    async def click_level_spin_if_present(frame_gray: np.ndarray) -> bool:
        search_top = int(frame_gray.shape[0] * LV_SPIN_SEARCH_TOP_RATIO)
        search_frame = frame_gray[search_top:, :]
        x, y, score = find_template(
            search_frame,
            lv_spin_template,
            lv_spin_template_path.name,
            scales=LV_SPIN_TEMPLATE_SCALES,
        )
        if score < LV_SPIN_TEMPLATE_THRESHOLD:
            return False

        y += search_top
        click_x = max(0, x + LV_SPIN_CLICK_OFFSET_X)
        print(
            f"Level spin interrupt at {x},{y}, score={score:.3f}; "
            f"clicking {click_x},{y}.",
            flush=True,
        )
        await _click(page, click_x, y)
        await page.wait_for_timeout(AUTOMAP_POLL_MS)
        return True

    async def level_spin_interrupt(
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        return await click_level_spin_if_present(frame_gray)

    async def map_end(_frame_bgr: np.ndarray, frame_gray: np.ndarray) -> bool:
        nonlocal last_map_end_check, map_completed
        now = loop.time()
        if (
            last_map_end_check is not None
            and now - last_map_end_check < MAP_END_CHECK_INTERVAL_SEC
        ):
            return False

        last_map_end_check = now
        x, y, score = find_template(
            frame_gray,
            map_end_template,
            map_end_template_path.name,
        )
        if score < MAP_END_TEMPLATE_THRESHOLD:
            return False

        print(
            f"Map end at {x},{y}, score={score:.3f}; clicking back to home.",
            flush=True,
        )
        await _click(page, x, y)
        map_completed = await finish_map_from_home()
        return True

    async def finish_map_from_home() -> bool:
        reward_clicked = False
        while stop_event is None or not stop_event.is_set():
            frame_bgr = await capture_page_bgr(page)
            frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

            if not reward_clicked:
                reward_matches = find_template_matches(
                    frame_gray,
                    win_reward_template,
                    win_reward_template_path.name,
                    threshold=WIN_REWARD_TEMPLATE_THRESHOLD,
                    scales=(1.0,),
                )
                if reward_matches:
                    x, y, score = reward_matches[0]
                    print(
                        f"Win reward at {x},{y}, score={score:.3f}; "
                        "clicking first match.",
                        flush=True,
                    )
                    await _click(page, x, y)
                    reward_clicked = True
                    await page.wait_for_timeout(AUTOMAP_POLL_MS)
                    continue

            x, y, score = find_template(
                frame_gray,
                start_home_template,
                start_home_template_path.name,
            )
            if score >= START_HOME_TEMPLATE_THRESHOLD:
                print(
                    f"Home ready at {x},{y}, score={score:.3f}; auto-map complete.",
                    flush=True,
                )
                return True

            await page.wait_for_timeout(AUTOMAP_POLL_MS)

        print("Auto-map flow stopped while waiting for home reward.", flush=True)
        return False

    async def protect_gate(frame_bgr: np.ndarray, _frame_gray: np.ndarray) -> bool:
        if not region_has_enough_white(frame_bgr):
            return False

        print("Protect gate available; clicking twice with 800ms delay.", flush=True)
        await _click(page, *PROTECT_CLICK)
        if not await wait_with_countdown(
            page, AUTOMAP_ACTION_DELAY_MS, "Protect gate", stop_event
        ):
            return True
        await _click(page, *PROTECT_CONFIRM_CLICK)
        return True

    async def level_up(_frame_bgr: np.ndarray, frame_gray: np.ndarray) -> bool:
        matches = find_template_matches(
            frame_gray,
            lv_up_template,
            lv_up_template_path.name,
            threshold=threshold,
        )
        if not matches:
            return False

        x, y, score = max(matches, key=lambda match: match[1])
        print(
            f"Level up at {x},{y}, score={score:.3f}; "
            f"clicking bottom-most match, then confirm in 800ms.",
            flush=True,
        )
        await _click(page, x, y)
        if not await wait_with_countdown(
            page, AUTOMAP_ACTION_DELAY_MS, "Level up", stop_event
        ):
            return True
        frame_bgr = await capture_page_bgr(page)
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if await click_level_spin_if_present(frame_gray):
            return True
        await _click(page, *UPGRADE_CONFIRM_CLICK)
        return True

    async def build_structure(
        _frame_bgr: np.ndarray,
        frame_gray: np.ndarray,
    ) -> bool:
        matches = find_template_matches(
            frame_gray,
            built_template,
            built_template_path.name,
            threshold=BUILT_TEMPLATE_THRESHOLD,
            scales=(1.0,),
        )
        if not matches:
            return False

        # Prefer the right-most marker, then the bottom-most marker when two
        # candidates share the same x coordinate.
        x, y, score = max(matches, key=lambda match: (match[0], match[1]))
        print(
            f"Build marker at {x},{y}, score={score:.3f}; "
            "clicking the highest-x/highest-y match.",
            flush=True,
        )
        await _click(page, x, y)
        if not await wait_with_countdown(
            page, AUTOMAP_ACTION_DELAY_MS, "Build menu", stop_event
        ):
            return True

        popup_frame = await capture_page_bgr(page)
        available_option = find_first_available_build_option(popup_frame)
        if available_option is not None:
            print("White-price build option is available; clicking it.", flush=True)
            await _click(page, *available_option)
            return True

        print("No white-price build option is available; skipping.", flush=True)
        return True

    handlers: tuple[SituationHandler, ...] = (
        level_spin_interrupt,
        map_end,
        protect_gate,
        level_up,
        build_structure,
        # Add future situations here in descending priority order.
    )

    while stop_event is None or not stop_event.is_set():
        frame_bgr = await capture_page_bgr(page)
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        for handler in handlers:
            if stop_event is not None and stop_event.is_set():
                break
            if await handler(frame_bgr, frame_gray):
                if handler is map_end:
                    if map_completed:
                        print("Auto-map flow completed; runner is idle.", flush=True)
                    return map_completed
                break
        else:
            await page.wait_for_timeout(AUTOMAP_POLL_MS)

    print("Auto-map flow stopped; runner is idle.", flush=True)
    return False

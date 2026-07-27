import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Optional

import cv2
import numpy as np

from hauntedroom.common import wait_with_countdown
from hauntedroom.cv_pattern_matching import (
    capture_page_bgr,
    capture_page_grayscale,
    find_template_matches,
    load_template,
)


AUTOMAP_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "rooms" / "automap"
LV_UP_TEMPLATE_PATH = AUTOMAP_TEMPLATE_DIR / "lv_up.png"
# lv_up.png excludes the two-pixel background border. The two valid icons in
# the captured battle UI score about 0.95 and 0.86; other UI stays below 0.60.
AUTOMAP_TEMPLATE_THRESHOLD = 0.80
AUTOMAP_POLL_MS = 400
AUTOMAP_ACTION_DELAY_MS = 800

PROTECT_REGION = (310, 640, 330, 655)
PROTECT_CLICK = (320, 640)
PROTECT_CONFIRM_CLICK = (357, 623)
UPGRADE_CONFIRM_CLICK = (430, 366)

SituationHandler = Callable[[], Awaitable[bool]]


def region_has_red(
    image: np.ndarray,
    region: tuple[int, int, int, int] = PROTECT_REGION,
) -> bool:
    """Detect a red unavailable indicator inside an x1,y1,x2,y2 region."""
    x1, y1, x2, y2 = region
    height, width = image.shape[:2]
    x1, x2 = max(0, x1), min(width, x2)
    y1, y2 = max(0, y1), min(height, y2)
    if x1 >= x2 or y1 >= y2:
        return False

    hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    hue, saturation, value = np.moveaxis(hsv, -1, 0)
    # OpenCV stores hue in [0, 179]. True red is close to either endpoint;
    # checking hue avoids treating the summon button's gold background as red.
    red_pixels = (
        ((hue <= 5) | (hue >= 175))
        & (saturation >= 100)
        & (value >= 120)
    )
    return bool(np.any(red_pixels))


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
) -> bool:
    """Run battle situations in priority order until stopped.

    A handler returns True after acting. The loop then starts again at the first
    handler, which lets a higher-priority situation preempt lower priorities.
    New battle situations can be appended to ``handlers`` without changing the
    scheduling loop.
    """
    lv_up_template = load_template(lv_up_template_path)

    async def protect_gate() -> bool:
        screenshot = await capture_page_bgr(page)
        if region_has_red(screenshot):
            return False

        print("Protect gate available; clicking twice with 800ms delay.", flush=True)
        await _click(page, *PROTECT_CLICK)
        if not await wait_with_countdown(
            page, AUTOMAP_ACTION_DELAY_MS, "Protect gate", stop_event
        ):
            return True
        await _click(page, *PROTECT_CONFIRM_CLICK)
        return True

    async def level_up() -> bool:
        screenshot = await capture_page_grayscale(page)
        matches = find_template_matches(
            screenshot,
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
        await _click(page, *UPGRADE_CONFIRM_CLICK)
        return True

    handlers: tuple[SituationHandler, ...] = (
        protect_gate,
        level_up,
        # Add future situations here in descending priority order.
    )

    while stop_event is None or not stop_event.is_set():
        for handler in handlers:
            if stop_event is not None and stop_event.is_set():
                break
            if await handler():
                break
        else:
            await page.wait_for_timeout(AUTOMAP_POLL_MS)

    print("Auto-map flow stopped; runner is idle.", flush=True)
    return False

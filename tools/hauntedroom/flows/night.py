"""Night challenge: enter, confirm solo, tap through battle, repeat 20 times."""

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.mouse import click_and_wait
from hauntedroom.core.runtime import flow_checkpoint
from hauntedroom.core.template_matching import find_template, load_template
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.vision.buttons import ButtonGeometry, find_red_yellow_button_pair


NIGHT_LOOP_COUNT = 20
NIGHT_INTERVAL_MS = 1_000
NIGHT_BATTLE_CLICK = (140, 680)
NIGHT_CANDLE_REGION = (205, 610, 265, 685)
NIGHT_CANDLE_THRESHOLD = 0.85
NIGHT_CANDLE_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "rooms"
    / "screen_detect"
    / "night_left_candle.png"
)
SOLO_BUTTON_GEOMETRY = ButtonGeometry(
    min_area=2_000,
    min_width=100,
    max_width=120,
    min_height=30,
    max_height=38,
    min_fill_ratio=0.60,
)


@lru_cache(maxsize=1)
def _candle_template() -> np.ndarray:
    return load_template(NIGHT_CANDLE_TEMPLATE)


def find_night_left_candle(frame: np.ndarray) -> Optional[tuple[int, int]]:
    """Match only the lit bottom-left candle, excluding dimmed popup scenery."""
    if frame.shape != (720, 640, 3):
        return None
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    template = _candle_template()
    x, y, score = find_template(
        gray,
        template,
        NIGHT_CANDLE_TEMPLATE.name,
        scales=(1.0,),
        region=NIGHT_CANDLE_REGION,
    )
    if score < NIGHT_CANDLE_THRESHOLD:
        return None
    height, width = template.shape
    left, top = x - width // 2, y - height // 2
    patch = gray[top : top + height, left : left + width]
    if float(patch.mean()) < float(template.mean()) * 0.70:
        return None
    return x, y


def find_night_solo_confirm(frame: np.ndarray) -> Optional[tuple[int, int]]:
    """Return yellow OK only when the solo dialog's full button pair is ready."""
    if frame.shape != (720, 640, 3):
        return None
    pair = find_red_yellow_button_pair(
        frame,
        (180, 440, 310, 490),
        (330, 440, 460, 490),
        SOLO_BUTTON_GEOMETRY,
        SOLO_BUTTON_GEOMETRY,
    )
    return pair.yellow.center if pair is not None else None


async def run_night_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
) -> bool:
    completed = 0
    entering = True
    candle_clicked = False
    while await flow_checkpoint(stop_event):
        frame = await capture_page_bgr(page)
        # Popup always wins over the background candle and battle tapping.
        confirm = find_night_solo_confirm(frame)
        candle = find_night_left_candle(frame)
        if confirm is not None:
            target = confirm
        elif entering:
            if candle is not None:
                target = candle
                candle_clicked = True
            elif candle_clicked:
                entering = False
                target = NIGHT_BATTLE_CLICK
            else:
                print("Night candle missing before entry; runner is idle.", flush=True)
                return False
        elif candle is not None:
            completed += 1
            print(f"Night loop {completed}/{NIGHT_LOOP_COUNT} completed.", flush=True)
            if completed >= NIGHT_LOOP_COUNT:
                return True
            entering = True
            candle_clicked = True
            target = candle
        else:
            target = NIGHT_BATTLE_CLICK

        if not await click_and_wait(page, target, NIGHT_INTERVAL_MS, stop_event):
            return False
    return False

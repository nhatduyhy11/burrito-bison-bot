"""Shift+4 train entry, five hero selections, then normal auto-battle."""

import asyncio
from typing import Awaitable, Callable, Optional

import cv2
import numpy as np

from hauntedroom.actions.models import Action, ClickTemplateAction
from hauntedroom.actions.runner import wait_for_template
from hauntedroom.core.runtime import flow_checkpoint, flow_time, wait_for_flow_timeout
from hauntedroom.core.template import load_template
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.boss_action import click
from hauntedroom.flows.automap_support.train_select import TrainHeroMatcher


TRAIN_AVAILABLE_REGION = (126, 196, 222, 213)
TRAIN_AVAILABLE_MIN_TEXT_PIXELS = 30
TRAIN_ENTRY_CLICK = (319, 129)
TRAIN_BATTLE_LOAD_MS = 5_000
TRAIN_SELECTION_ROUNDS = 5
TRAIN_SELECTION_POLL_MS = 200
TRAIN_SELECTION_SETTLE_MS = 600
TRAIN_SELECTION_TIMEOUT_MS = 30_000


def train_is_available(frame_bgr: np.ndarray) -> bool:
    """Read the green `Lượt vượt ải` row without OCR."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[:2] != (720, 640):
        return False
    left, top, right, bottom = TRAIN_AVAILABLE_REGION
    hsv = cv2.cvtColor(frame_bgr[top:bottom, left:right], cv2.COLOR_BGR2HSV)
    available_text = (
        (hsv[:, :, 0] >= 14)
        & (hsv[:, :, 0] <= 25)
        & (hsv[:, :, 1] >= 100)
        & (hsv[:, :, 2] >= 80)
    )
    return int(np.count_nonzero(available_text)) >= TRAIN_AVAILABLE_MIN_TEXT_PIXELS


def get_start_battle_action(actions: list[Action]) -> ClickTemplateAction:
    for action in actions:
        if (
            isinstance(action, ClickTemplateAction)
            and action.template_path.name == "start_battle.png"
        ):
            return action
    raise ValueError("Actions do not contain start_battle.png for train mode.")


async def run_train_flow(
    page,
    actions: list[Action],
    automap_flow: Callable[..., Awaitable[bool]],
    stop_event: Optional[asyncio.Event] = None,
    debug: bool = False,
) -> bool:
    """Enter an available train, select 2 cards five times, then auto-battle."""
    frame_bgr = await capture_page_bgr(page)
    if not train_is_available(frame_bgr):
        print("No train attempt is currently available; runner is idle.", flush=True)
        return False

    print(f"Train attempt available; entering at {TRAIN_ENTRY_CLICK}.", flush=True)
    await click(page, *TRAIN_ENTRY_CLICK)

    action = get_start_battle_action(actions)
    template_path = action.template_path
    start_battle = load_template(template_path)
    match = await wait_for_template(
        page,
        start_battle,
        template_path.name,
        float(action.threshold),
        int(action.timeout_ms),
        int(action.poll_ms),
        stop_event,
        click_position=action.click_position,
        template_scales=action.template_scales,
    )
    if match is None:
        return False
    x, y, score = match
    print(f"Train start battle at {x},{y}, score={score:.3f}; clicking.", flush=True)
    await click(page, x, y)
    if not await wait_for_flow_timeout(page, TRAIN_BATTLE_LOAD_MS, stop_event):
        return False

    matcher = TrainHeroMatcher()
    confirmed_rounds = 0
    deadline = flow_time(stop_event) + TRAIN_SELECTION_TIMEOUT_MS / 1000
    while confirmed_rounds < TRAIN_SELECTION_ROUNDS:
        if not await flow_checkpoint(stop_event):
            return False
        choice = matcher.find_choice(await capture_page_bgr(page))
        if choice is None:
            if flow_time(stop_event) >= deadline:
                raise TimeoutError(
                    "Timed out during train hero selection; "
                    f"confirmed {confirmed_rounds}/{TRAIN_SELECTION_ROUNDS}."
                )
            if not await wait_for_flow_timeout(
                page, TRAIN_SELECTION_POLL_MS, stop_event
            ):
                return False
            continue

        if choice.confirm:
            confirmed_rounds += 1
            deadline = flow_time(stop_event) + TRAIN_SELECTION_TIMEOUT_MS / 1000
            print(
                f"Train hero selection {confirmed_rounds}/"
                f"{TRAIN_SELECTION_ROUNDS}: confirming 2 cards.",
                flush=True,
            )
        elif choice.template_name is not None:
            print(
                f"Train option {choice.template_name!r} matched at "
                f"{choice.x},{choice.y}, score={choice.score:.3f}.",
                flush=True,
            )
        else:
            print(
                f"Train priority missed; choosing purple card at "
                f"{choice.x},{choice.y}.",
                flush=True,
            )
        await click(page, choice.x, choice.y)
        if not await wait_for_flow_timeout(
            page, TRAIN_SELECTION_SETTLE_MS, stop_event
        ):
            return False

    print("All 5 train selections confirmed; starting normal auto-battle.", flush=True)
    return await automap_flow(page, stop_event, debug=debug)

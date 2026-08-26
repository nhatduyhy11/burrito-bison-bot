"""Collect every available diamond across the three collection tabs."""

import asyncio
from typing import Optional

import cv2

from hauntedroom.core.mouse import click_and_wait, scroll_and_wait
from hauntedroom.core.runtime import flow_checkpoint, wait_for_flow_timeout
from hauntedroom.core.template_matching import load_template
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.diamond_collection_vision import (
    DIAMOND_CLOSE_TEMPLATE_PATH,
    DIAMOND_REWARD_TEMPLATE_PATH,
    find_diamond_content_mark,
    find_diamond_popup_close,
    find_diamond_popup_reward,
    find_diamond_tabs,
)


DIAMOND_SETTLE_MS = 800
DIAMOND_SCROLL_AMOUNT = 527
DIAMOND_SCROLL_POSITION = (320, 500)
DIAMOND_MAX_SCROLLS_PER_TAB = 20
DIAMOND_POPUP_MAX_ATTEMPTS = 4
DIAMOND_REWARD_REPEAT_MS = 1000
DIAMOND_RESERVE_CLICK_Y_OFFSET = 40
DIAMOND_RESERVE_CLICK_COUNT = 2


async def _collect_detail_popup(
    page,
    close_template,
    reward_template,
    stop_event,
    delay_ms: int,
) -> Optional[int]:
    """Collect a popup reward if present, then close the detail popup."""
    reward_collected = False
    for attempt in range(1, DIAMOND_POPUP_MAX_ATTEMPTS + 1):
        if not await flow_checkpoint(stop_event):
            return None

        frame_bgr = await capture_page_bgr(page)
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if not reward_collected:
            reward = find_diamond_popup_reward(frame_gray, reward_template)
        else:
            reward = None
        if reward is not None:
            reward_x, reward_y, reward_score = reward
            reserve_position = (
                reward_x,
                reward_y + DIAMOND_RESERVE_CLICK_Y_OFFSET,
            )
            print(
                f"Diamond popup reward at {reward_x},{reward_y}, "
                f"score={reward_score:.3f}; clicking diamond once, then "
                f"{reserve_position[0]},{reserve_position[1]} below it "
                f"{DIAMOND_RESERVE_CLICK_COUNT} times with a "
                f"{DIAMOND_REWARD_REPEAT_MS}ms gap after every click.",
                flush=True,
            )
            if not await click_and_wait(
                page,
                (reward_x, reward_y),
                DIAMOND_REWARD_REPEAT_MS,
                stop_event,
            ):
                return None
            if not await click_and_wait(
                page,
                reserve_position,
                DIAMOND_REWARD_REPEAT_MS,
                stop_event,
                click_count=DIAMOND_RESERVE_CLICK_COUNT,
            ):
                return None
            reward_collected = True
            continue

        close = find_diamond_popup_close(
            frame_gray, close_template
        )
        if close is not None:
            close_x, close_y, close_score = close
            print(
                f"Diamond detail close at {close_x},{close_y}, "
                f"score={close_score:.3f}; closing.",
                flush=True,
            )
            if not await click_and_wait(
                page, (close_x, close_y), delay_ms, stop_event
            ):
                return None
            return int(reward_collected)

        print(
            "Diamond detail popup not ready "
            f"({attempt}/{DIAMOND_POPUP_MAX_ATTEMPTS}); rechecking.",
            flush=True,
        )
        if not await wait_for_flow_timeout(page, delay_ms, stop_event):
            return None

    print("Diamond detail popup could not be detected; stopping safely.", flush=True)
    return None


async def run_diamond_collection_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
    delay_ms: int = DIAMOND_SETTLE_MS,
) -> bool:
    """Drain marked cards tab-by-tab, scrolling until each tab badge clears."""
    close_template = load_template(DIAMOND_CLOSE_TEMPLATE_PATH)
    reward_template = load_template(DIAMOND_REWARD_TEMPLATE_PATH)
    collected = 0

    while await flow_checkpoint(stop_event):
        tabs = find_diamond_tabs(await capture_page_bgr(page))
        if not tabs:
            print(
                f"No diamond collection tabs are marked; collected {collected}. "
                "Runner is idle.",
                flush=True,
            )
            return True

        tab_index, tab_x, tab_y = tabs[0]
        print(
            f"Diamond collection tab {tab_index + 1} is marked; "
            f"opening at {tab_x},{tab_y}.",
            flush=True,
        )
        if not await click_and_wait(
            page, (tab_x, tab_y), delay_ms, stop_event
        ):
            return False

        scroll_count = 0
        while await flow_checkpoint(stop_event):
            frame_bgr = await capture_page_bgr(page)
            content = find_diamond_content_mark(frame_bgr)
            if content is not None:
                print(
                    f"Diamond collection card marked at "
                    f"{content[0]},{content[1]}; opening detail.",
                    flush=True,
                )
                if not await click_and_wait(
                    page, content, delay_ms, stop_event
                ):
                    return False
                popup_collected = await _collect_detail_popup(
                    page,
                    close_template,
                    reward_template,
                    stop_event,
                    delay_ms,
                )
                if popup_collected is None:
                    return False
                collected += popup_collected
                continue

            marked_tabs = {
                marked_index for marked_index, _x, _y in find_diamond_tabs(frame_bgr)
            }
            if tab_index not in marked_tabs:
                print(
                    f"Diamond collection tab {tab_index + 1} is complete.",
                    flush=True,
                )
                break

            scroll_count += 1
            if scroll_count > DIAMOND_MAX_SCROLLS_PER_TAB:
                print(
                    f"Diamond collection tab {tab_index + 1} stayed marked "
                    f"after {DIAMOND_MAX_SCROLLS_PER_TAB} scrolls; stopping safely.",
                    flush=True,
                )
                return False
            print(
                f"No visible mark in tab {tab_index + 1}; scrolling down "
                f"({scroll_count}/{DIAMOND_MAX_SCROLLS_PER_TAB}).",
                flush=True,
            )
            if not await scroll_and_wait(
                page,
                DIAMOND_SCROLL_POSITION,
                DIAMOND_SCROLL_AMOUNT,
                delay_ms,
                stop_event,
            ):
                return False

    print("Diamond collection flow stopped; runner is idle.", flush=True)
    return False

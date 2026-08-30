"""Clear the two new-account prompts, then hand off to normal auto-map."""

import asyncio
from typing import Awaitable, Callable, Optional

from hauntedroom.actions.builder import build_spawn_exit_lvup_actions
from hauntedroom.actions.runner import run_actions
from hauntedroom.core.mouse import click_and_wait
from hauntedroom.core.runtime import flow_checkpoint, flow_time, wait_for_flow_timeout
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.screen_detect import (
    NEW_ACCOUNT_ACTION_CLICK,
    ScreenName,
    detect_screen,
)


NEW_ACCOUNT_CLICK_DELAY_MS = 1_000
NEW_ACCOUNT_POLL_MS = 500
NEW_ACCOUNT_TIMEOUT_MS = 60_000


async def run_new_account_flow(
    page,
    automap_flow: Callable[..., Awaitable[bool]],
    stop_event: Optional[asyncio.Event] = None,
    debug: bool = False,
    *,
    run_state: Optional[object] = None,
) -> bool:
    """Click the shared action point until the normal auto-map screen appears."""
    deadline = flow_time(stop_event) + NEW_ACCOUNT_TIMEOUT_MS / 1_000
    click_count = 0

    while await flow_checkpoint(stop_event):
        screen = detect_screen(await capture_page_bgr(page))
        if screen is ScreenName.NEW_ACCOUNT:
            click_count += 1
            print(
                "New-account action detected; clicking shared point "
                f"{NEW_ACCOUNT_ACTION_CLICK} (click {click_count}).",
                flush=True,
            )
            if not await click_and_wait(
                page,
                NEW_ACCOUNT_ACTION_CLICK,
                NEW_ACCOUNT_CLICK_DELAY_MS,
                stop_event,
            ):
                return False
            continue

        if screen is ScreenName.AUTOMAP:
            print(
                "New-account setup finished; starting normal auto-map.",
                flush=True,
            )
            automap_completed = await automap_flow(
                page,
                stop_event,
                debug=debug,
                run_state=run_state,
                new_account_lubu_popup_active=True,
                capture_hero_fallback_screenshots=False,
            )
            if not automap_completed:
                return False

            print(
                "First map completed; executing one-time enter-exit map flow.",
                flush=True,
            )
            spawn_exit_actions = build_spawn_exit_lvup_actions()
            return await run_actions(
                page,
                spawn_exit_actions,
                loop_count=1,
                stop_event=stop_event,
                loop_label="new_account enter-exit map",
            )

        if flow_time(stop_event) >= deadline:
            raise TimeoutError(
                "Timed out waiting for new-account setup to reach auto-map."
            )
        if not await wait_for_flow_timeout(page, NEW_ACCOUNT_POLL_MS, stop_event):
            return False

    return False

"""Unified Train Flow supporting 3 execution modes:

1. NORMAL: Enter train -> 5 hero card selections -> full normal auto-battle.
2. EXIT_IMMEDIATELY: Enter train -> 5 hero selections -> wait match start -> exit immediately.
3. PET_AND_AD: Enter train -> 5 hero selections -> wait match start -> active pet + summon + wait spin -> exit.
"""

import asyncio
from typing import Awaitable, Callable, Optional, Union

from hauntedroom.flows.train_support.common import TrainMode
from hauntedroom.flows.train_support.entry import (
    check_and_click_train_challenge,
    wait_and_click_start_battle,
)
from hauntedroom.flows.train_support.exit_flow import (
    run_train_ad_exit_cycle,
    run_train_ad_exit_loop,
)
from hauntedroom.flows.train_support.hero_selection import select_train_heroes


def _normalize_mode(
    mode: Union[TrainMode, str, None],
    pet_and_ad: Optional[bool] = None,
) -> TrainMode:
    """Normalize input parameters into a TrainMode enum value."""
    if pet_and_ad is not None:
        return TrainMode.PET_AND_AD if pet_and_ad else TrainMode.EXIT_IMMEDIATELY
    if mode is None:
        return TrainMode.NORMAL
    if isinstance(mode, TrainMode):
        return mode
    if isinstance(mode, str):
        mode_key = mode.lower().strip().replace("-", "_")
        if mode_key in ("normal", "train", "standard"):
            return TrainMode.NORMAL
        elif mode_key in ("exit_immediately", "immediate_exit", "exit_early", "direct_exit", "exit"):
            return TrainMode.EXIT_IMMEDIATELY
        elif mode_key in ("pet_and_ad", "pet_ad", "pet", "ad_exit", "pet_and_spin"):
            return TrainMode.PET_AND_AD
        raise ValueError(f"Unknown train mode: {mode!r}. Valid modes are: NORMAL, EXIT_IMMEDIATELY, PET_AND_AD")
    return mode


async def run_train_flow(
    page,
    automap_flow: Optional[Callable[..., Awaitable[bool]]] = None,
    stop_event: Optional[asyncio.Event] = None,
    debug: bool = False,
    *,
    run_state: Optional[object] = None,
    mode: Union[TrainMode, str] = TrainMode.NORMAL,
    loop: Optional[bool] = None,
    pet_and_ad: Optional[bool] = None,
) -> bool:
    """Run train flow in one of 3 modes:

    - TrainMode.NORMAL (default):
        Enter challenge -> start battle -> 5 hero selections -> normal auto-battle.
    - TrainMode.EXIT_IMMEDIATELY:
        Enter challenge -> start battle -> 5 hero selections -> wait match start -> exit immediately.
    - TrainMode.PET_AND_AD:
        Enter challenge -> start battle -> 5 hero selections -> wait match start -> activate middle pet,
        summon repeatedly, wait for level spin & dismiss -> exit.
    """
    selected_mode = _normalize_mode(mode, pet_and_ad)

    if selected_mode is TrainMode.NORMAL and automap_flow is None:
        raise ValueError("automap_flow is required for normal train mode")

    # 1. Mode: NORMAL (full normal train flow)
    if selected_mode is TrainMode.NORMAL:
        if not await check_and_click_train_challenge(page, stop_event):
            return False

        if not await wait_and_click_start_battle(page, stop_event):
            return False

        if not await select_train_heroes(page, stop_event, raise_on_timeout=True):
            return False

        print("All 5 train selections confirmed; starting normal auto-battle.", flush=True)
        return await automap_flow(
            page,
            stop_event,
            debug=debug,
            run_state=run_state,
        )

    # 2 & 3. Modes: EXIT_IMMEDIATELY / PET_AND_AD
    is_pet_mode = (selected_mode is TrainMode.PET_AND_AD)
    is_loop = False if loop is False else True  # Default to looping for ad-exit flows unless loop=False

    if is_loop:
        return await run_train_ad_exit_loop(
            page,
            stop_event,
            debug=debug,
            pet_and_ad=is_pet_mode,
        )
    return await run_train_ad_exit_cycle(
        page,
        stop_event,
        pet_and_ad=is_pet_mode,
    )


async def run_train_ad_exit_flow(
    page,
    stop_event: Optional[asyncio.Event] = None,
    debug: bool = False,
    *,
    pet_and_ad: bool = True,
) -> bool:
    """Convenience wrapper delegating to run_train_flow for ad-exit modes."""
    mode = TrainMode.PET_AND_AD if pet_and_ad else TrainMode.EXIT_IMMEDIATELY
    return await run_train_flow(
        page,
        stop_event=stop_event,
        debug=debug,
        mode=mode,
        loop=True,
    )

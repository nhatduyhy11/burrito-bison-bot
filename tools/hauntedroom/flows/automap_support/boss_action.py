"""Boss-specific actions used by the auto-map battle flow."""

from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.core.mouse import bot_click, click_and_wait
from hauntedroom.core.runtime import flow_checkpoint
from hauntedroom.core.template import load_bgr_reference
from hauntedroom.core.terminal import GREEN, ORANGE, colorize
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.vision.boss_controls import (
    boss_spell_is_ready,
    find_active_pet_summon,
    find_ready_boss_pet,
)

ROOM_TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "rooms"
BOSS_TEMPLATE_DIR = ROOM_TEMPLATE_DIR / "boss"
PET_ACTIVE_TEMPLATE_PATH = BOSS_TEMPLATE_DIR / "pet_active.png"

PET_READY_CLICK_OFFSET_Y = 15
SPELL_ACTION_POSITION = (488, 584)
BOSS_ACTION_SELECT_DELAY_MS = 200
PET_MENU_RECHECK_MS = 300
PET_ACTIVE_TEMPLATE_THRESHOLD = 0.90


async def activate_boss_spell(
    page,
    boss_position: tuple[int, int],
    frame_bgr: Optional[np.ndarray] = None,
) -> bool:
    """Select and target the boss spell when its electric glow is ready."""
    if frame_bgr is None:
        frame_bgr = await capture_page_bgr(page)
    if not boss_spell_is_ready(frame_bgr):
        return False

    print("Boss spell is ready; selecting it and targeting the boss.", flush=True)
    await click_and_wait(page, SPELL_ACTION_POSITION, BOSS_ACTION_SELECT_DELAY_MS)
    await bot_click(page, boss_position)
    return True


async def deploy_boss_pet(
    page,
    boss_position: Optional[tuple[int, int]] = None,
    frame_bgr: Optional[np.ndarray] = None,
    active_reference: Optional[np.ndarray] = None,
    stop_event=None,
) -> bool:
    """Open the ready pet menu, confirm its summon action, and close it.

    ``boss_position`` remains accepted for callers using the old drag API, but
    the current game UI summons the pet through the popup instead.
    """
    if frame_bgr is None:
        frame_bgr = await capture_page_bgr(page)
    ready_bar = find_ready_boss_pet(frame_bgr)
    if ready_bar is None:
        return False
    ready_bar_x, ready_bar_y = ready_bar.center
    pet_click = (ready_bar_x, ready_bar_y - PET_READY_CLICK_OFFSET_Y)

    if active_reference is None:
        active_reference = load_bgr_reference(PET_ACTIVE_TEMPLATE_PATH)
    print(
        colorize(
            f"Final-boss pet has a full glowing bar at "
            f"{ready_bar_x},{ready_bar_y}; opening its menu at "
            f"{pet_click[0]},{pet_click[1]}.",
            ORANGE,
        ),
        flush=True,
    )
    while await flow_checkpoint(stop_event):
        if not await click_and_wait(
            page, pet_click, PET_MENU_RECHECK_MS, stop_event
        ):
            break

        popup_frame = await capture_page_bgr(page)
        active_match = find_active_pet_summon(
            popup_frame,
            active_reference,
            PET_ACTIVE_TEMPLATE_PATH.name,
        )
        if active_match is None:
            return False
        active_x, active_y, active_score = active_match
        if active_score >= PET_ACTIVE_TEMPLATE_THRESHOLD:
            print(
                colorize(
                    f"Pet summon is active at {active_x},{active_y}, "
                    f"score={active_score:.3f}; clicking it.",
                    GREEN,
                ),
                flush=True,
            )
            await bot_click(page, (active_x, active_y))
            return True

        print(
            f"Pet summon is not active yet (score={active_score:.3f}); "
            "clicking above the detected ready bar again.",
            flush=True,
        )

    return False

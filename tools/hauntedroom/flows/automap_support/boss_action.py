"""Boss-specific actions used by the auto-map battle flow."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.runtime import flow_checkpoint, wait_for_flow_timeout
from hauntedroom.core.template import find_template, load_bgr_reference
from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.automap_support.boss_detector import (
    PET_READY_REGION,
    SPELL_READY_REGION,
    boss_action_has_ready_glow,
)


ROOM_TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "rooms"
BOSS_TEMPLATE_DIR = ROOM_TEMPLATE_DIR / "boss"
PET_READY_TEMPLATE_PATH = BOSS_TEMPLATE_DIR / "pet_ready.png"
PET_ACTIVE_TEMPLATE_PATH = BOSS_TEMPLATE_DIR / "pet_active.png"
SPELL_READY_TEMPLATE_PATH = BOSS_TEMPLATE_DIR / "spell_ready.png"

PET_ACTION_POSITION = (319, 603)
SPELL_ACTION_POSITION = (488, 584)
BOSS_ACTION_SELECT_DELAY_MS = 200
BOSS_PET_DRAG_STEPS = 10
PET_MENU_RECHECK_MS = 300
PET_TEMPLATE_THRESHOLD = 0.90


@dataclass(frozen=True)
class BossActionReferences:
    pet_ready: np.ndarray
    pet_active: np.ndarray
    spell_ready: np.ndarray


def load_boss_action_references() -> BossActionReferences:
    """Load immutable boss-action references once for an auto-map run."""
    return BossActionReferences(
        pet_ready=load_bgr_reference(PET_READY_TEMPLATE_PATH),
        pet_active=load_bgr_reference(PET_ACTIVE_TEMPLATE_PATH),
        spell_ready=load_bgr_reference(SPELL_READY_TEMPLATE_PATH),
    )


async def click(page, x: int, y: int) -> None:
    """Click without recording the bot-generated input as a user action."""
    await page.evaluate(
        "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
    )
    await page.mouse.click(x, y)


async def activate_boss_spell(
    page,
    boss_position: tuple[int, int],
    frame_bgr: Optional[np.ndarray] = None,
    ready_reference: Optional[np.ndarray] = None,
) -> bool:
    """Select and target the boss spell when its electric glow is ready."""
    if frame_bgr is None:
        frame_bgr = await capture_page_bgr(page)
    if ready_reference is None:
        ready_reference = load_bgr_reference(SPELL_READY_TEMPLATE_PATH)
    if not boss_action_has_ready_glow(
        frame_bgr,
        ready_reference,
        SPELL_READY_REGION,
    ):
        return False

    print("Boss spell is ready; selecting it and targeting the boss.", flush=True)
    await click(page, *SPELL_ACTION_POSITION)
    await page.wait_for_timeout(BOSS_ACTION_SELECT_DELAY_MS)
    await click(page, *boss_position)
    return True


async def deploy_boss_pet(
    page,
    boss_position: Optional[tuple[int, int]] = None,
    frame_bgr: Optional[np.ndarray] = None,
    ready_reference: Optional[np.ndarray] = None,
    active_reference: Optional[np.ndarray] = None,
    stop_event=None,
) -> bool:
    """Open the ready pet menu, confirm its summon action, and close it.

    ``boss_position`` remains accepted for callers using the old drag API, but
    the current game UI summons the pet through the popup instead.
    """
    if frame_bgr is None:
        frame_bgr = await capture_page_bgr(page)
    if ready_reference is None:
        ready_reference = load_bgr_reference(PET_READY_TEMPLATE_PATH)
    frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    ready_gray = cv2.cvtColor(ready_reference, cv2.COLOR_BGR2GRAY)
    ready_x, ready_y, ready_score = find_template(
        frame_gray,
        ready_gray,
        PET_READY_TEMPLATE_PATH.name,
        scales=(1.0,),
    )
    if ready_score < PET_TEMPLATE_THRESHOLD:
        return False

    if active_reference is None:
        active_reference = load_bgr_reference(PET_ACTIVE_TEMPLATE_PATH)
    active_gray = cv2.cvtColor(active_reference, cv2.COLOR_BGR2GRAY)
    print(
        f"Final-boss pet is ready at {ready_x},{ready_y}, "
        f"score={ready_score:.3f}; opening its menu.",
        flush=True,
    )
    while await flow_checkpoint(stop_event):
        await click(page, ready_x, ready_y)
        if not await wait_for_flow_timeout(page, PET_MENU_RECHECK_MS, stop_event):
            break

        popup_frame = await capture_page_bgr(page)
        active_x, active_y, active_score = find_template(
            cv2.cvtColor(popup_frame, cv2.COLOR_BGR2GRAY),
            active_gray,
            PET_ACTIVE_TEMPLATE_PATH.name,
            scales=(1.0,),
        )
        if active_score >= PET_TEMPLATE_THRESHOLD:
            print(
                f"Pet summon is active at {active_x},{active_y}, "
                f"score={active_score:.3f}; clicking it.",
                flush=True,
            )
            await click(page, active_x, active_y)
            return True

        print(
            f"Pet summon is not active yet (score={active_score:.3f}); "
            "clicking pet_ready again.",
            flush=True,
        )

    return False

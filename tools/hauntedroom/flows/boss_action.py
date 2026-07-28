"""Boss-specific actions used by the auto-map battle flow."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.core.vision import capture_page_bgr
from hauntedroom.flows.map_vision_helper import (
    PET_READY_REGION,
    SPELL_READY_REGION,
    boss_action_has_ready_glow,
    load_bgr_reference,
)


ROOM_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "rooms"
BOSS_TEMPLATE_DIR = ROOM_TEMPLATE_DIR / "boss"
PET_READY_TEMPLATE_PATH = BOSS_TEMPLATE_DIR / "pet_ready.png"
SPELL_READY_TEMPLATE_PATH = BOSS_TEMPLATE_DIR / "spell_ready.png"

PET_ACTION_POSITION = (319, 603)
SPELL_ACTION_POSITION = (488, 584)
BOSS_ACTION_SELECT_DELAY_MS = 200
BOSS_PET_DRAG_STEPS = 10


@dataclass(frozen=True)
class BossActionReferences:
    pet_ready: np.ndarray
    spell_ready: np.ndarray


def load_boss_action_references() -> BossActionReferences:
    """Load immutable boss-action references once for an auto-map run."""
    return BossActionReferences(
        pet_ready=load_bgr_reference(PET_READY_TEMPLATE_PATH),
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
    boss_position: tuple[int, int],
    frame_bgr: Optional[np.ndarray] = None,
    ready_reference: Optional[np.ndarray] = None,
) -> bool:
    """Drag the ready pet card onto the boss."""
    if frame_bgr is None:
        frame_bgr = await capture_page_bgr(page)
    if ready_reference is None:
        ready_reference = load_bgr_reference(PET_READY_TEMPLATE_PATH)
    if not boss_action_has_ready_glow(
        frame_bgr,
        ready_reference,
        PET_READY_REGION,
    ):
        return False

    print("Boss pet is ready; dragging it onto the boss.", flush=True)
    await page.evaluate(
        "() => { window.__hauntedRoomSuppressNextClickLog = true; }"
    )
    await page.mouse.move(*PET_ACTION_POSITION)
    await page.mouse.down()
    await page.mouse.move(*boss_position, steps=BOSS_PET_DRAG_STEPS)
    await page.mouse.up()
    return True

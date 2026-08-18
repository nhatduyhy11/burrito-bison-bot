"""Visual queries for boss-specific action controls."""

from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.template import find_template
from hauntedroom.core.vision import (
    ColorComponentMatch,
    ColorComponentPattern,
    find_color_component,
    region_has_color_component,
)

# Both controls have a bright yellow/orange ready glow in fixed UI slots. The
# pet region spans the complete late-game cluster because the UI can show one
# to three pets. The pattern still requires a full-width energy bar, so empty
# slots, partially charged pets, and the artwork above each bar are ignored.
PET_READY_REGION = (250, 574, 390, 632)
SPELL_READY_REGION = (450, 542, 522, 623)
PET_READY_GLOW_PATTERN = ColorComponentPattern(
    lower_hsv=(15, 120, 180),
    upper_hsv=(40, 255, 255),
    min_area=250,
    min_width=35,
    max_width=45,
    min_height=8,
    max_height=14,
    min_fill_ratio=0.65,
)
SPELL_READY_GLOW_PATTERN = ColorComponentPattern(
    lower_hsv=(15, 120, 180),
    upper_hsv=(40, 255, 255),
    min_area=400,
)


def boss_spell_is_ready(frame_bgr: np.ndarray) -> bool:
    """Return whether the fixed boss-spell slot has its ready glow."""
    return region_has_color_component(
        frame_bgr,
        SPELL_READY_REGION,
        SPELL_READY_GLOW_PATTERN,
    )


def find_ready_boss_pet(
    frame_bgr: np.ndarray,
) -> Optional[ColorComponentMatch]:
    """Return the ready energy bar for the final-boss pet, when present."""
    return find_color_component(
        frame_bgr,
        PET_READY_REGION,
        PET_READY_GLOW_PATTERN,
    )


def find_active_pet_summon(
    frame_bgr: np.ndarray,
    active_reference_bgr: np.ndarray,
    template_name: str,
) -> Optional[tuple[int, int, float]]:
    """Locate the active summon control in an opened pet popup."""
    if (
        frame_bgr.ndim != 3
        or frame_bgr.shape[2] != 3
        or active_reference_bgr.ndim != 3
        or active_reference_bgr.shape[2] != 3
    ):
        return None
    return find_template(
        cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(active_reference_bgr, cv2.COLOR_BGR2GRAY),
        template_name,
        scales=(1.0,),
    )

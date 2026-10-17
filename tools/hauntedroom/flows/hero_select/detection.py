"""Locale-free hero-select screen and battle-button detection.

Both lobbies (map and train) hand off to the hero-select phase at the same
signal: the locale-free top banner plus the yellow start button in the same
frame. This module is the single source for that detection; lobby recovery
and wait loops stay with the callers.
"""

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.template_matching import find_template
from hauntedroom.core.vision import ColorComponentMatch
from hauntedroom.vision.buttons import ButtonGeometry, find_colored_button

ROOMS_DIR = Path(__file__).resolve().parents[3] / "rooms"
HEADER_TEMPLATE_PATH = ROOMS_DIR / "hero_select_battle_banner_top.png"

# The title text changes by locale. Match only the thin, text-free top edge of
# its backing plate, restricted to the fixed top-screen neighborhood. The
# reference also contains scenery above/left of the plate, which can still be
# black while game assets load. Exclude that scenery from the comparison.
HERO_SELECT_HEADER_TEMPLATE_REGION = (8, 14, 47, 23)
HERO_SELECT_HEADER_REGION = (210, 10, 430, 90)
HERO_SELECT_HEADER_THRESHOLD = 0.80
HERO_SELECT_HEADER_SCALES = (1.0,)
HERO_SELECT_BATTLE_BUTTON_REGION = (230, 650, 410, 719)
HERO_SELECT_BATTLE_BUTTON_GEOMETRY = ButtonGeometry(
    min_area=2_400,
    min_width=95,
    max_width=130,
    min_height=28,
    max_height=45,
    min_fill_ratio=0.65,
)


def find_battle_button(
    image: np.ndarray,
    header_template: np.ndarray,
) -> Optional[ColorComponentMatch]:
    """Return the yellow start button only on the hero-select screen."""
    if image.ndim != 3 or image.shape[2] != 3:
        return None
    left, top, right, bottom = HERO_SELECT_HEADER_TEMPLATE_REGION
    header_edge = header_template[top:bottom, left:right]
    screenshot_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, _, header_score = find_template(
        screenshot_gray,
        header_edge,
        HEADER_TEMPLATE_PATH.name,
        scales=HERO_SELECT_HEADER_SCALES,
        region=HERO_SELECT_HEADER_REGION,
    )
    if header_score < HERO_SELECT_HEADER_THRESHOLD:
        return None
    return find_colored_button(
        image,
        HERO_SELECT_BATTLE_BUTTON_REGION,
        "yellow",
        HERO_SELECT_BATTLE_BUTTON_GEOMETRY,
    )

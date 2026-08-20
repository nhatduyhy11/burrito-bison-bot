"""Image detection helpers for the artifact flow."""

from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.core.template_matching import (
    TemplateMatch,
    find_template,
    find_template_in_region,
)


ROOMS_DIR = Path(__file__).resolve().parents[2] / "rooms"
ARTIFACT_MARK_TEMPLATE_PATH = ROOMS_DIR / "misc" / "research_available.png"
ARTIFACT_CLOSE_TEMPLATE_PATH = ROOMS_DIR / "blocker" / "lubu_close.png"

# The artifact screen has four fixed rarity tabs and ten fixed content slots.
# Keeping the searches inside these regions prevents notification marks in the
# bottom navigation from being mistaken for artifact availability.
ARTIFACT_TAB_REGIONS = (
    (150, 340, 248, 385),
    (245, 340, 325, 385),
    (325, 340, 405, 385),
    (405, 340, 490, 385),
)
ARTIFACT_CONTENT_REGION = (120, 390, 520, 600)
ARTIFACT_ACTIVATE_REGION = (220, 540, 420, 620)

ARTIFACT_TAB_SCALE = (0.8,)
ARTIFACT_CONTENT_SCALE = (0.9,)
ARTIFACT_ACTIVATE_SCALE = (0.5,)
ARTIFACT_CLOSE_SCALE = (1.0,)
ARTIFACT_TAB_THRESHOLD = 0.70
ARTIFACT_CONTENT_THRESHOLD = 0.80
ARTIFACT_ACTIVATE_THRESHOLD = 0.60
ARTIFACT_CLOSE_THRESHOLD = 0.90


def find_artifact_tabs(
    frame: np.ndarray,
    mark_template: np.ndarray,
) -> list[tuple[int, int, int, float]]:
    """Return marked rarity tabs from left to right."""
    matches = []
    for tab_index, region in enumerate(ARTIFACT_TAB_REGIONS):
        match = find_template_in_region(
            frame,
            mark_template,
            ARTIFACT_MARK_TEMPLATE_PATH.name,
            region,
            ARTIFACT_TAB_THRESHOLD,
            click_position="bottom_left",
            scales=ARTIFACT_TAB_SCALE,
        )
        if match is not None:
            matches.append((tab_index, *match))
    return matches


def find_artifact_item(
    frame: np.ndarray,
    mark_template: np.ndarray,
) -> Optional[TemplateMatch]:
    """Return one marked artifact card, offset into the card for clicking."""
    return find_template_in_region(
        frame,
        mark_template,
        ARTIFACT_MARK_TEMPLATE_PATH.name,
        ARTIFACT_CONTENT_REGION,
        ARTIFACT_CONTENT_THRESHOLD,
        click_position="bottom_left",
        scales=ARTIFACT_CONTENT_SCALE,
    )


def find_artifact_activation(
    frame: np.ndarray,
    mark_template: np.ndarray,
) -> Optional[TemplateMatch]:
    """Return the marked Activate button inside the artifact popup."""
    return find_template_in_region(
        frame,
        mark_template,
        ARTIFACT_MARK_TEMPLATE_PATH.name,
        ARTIFACT_ACTIVATE_REGION,
        ARTIFACT_ACTIVATE_THRESHOLD,
        click_position="bottom_left",
        scales=ARTIFACT_ACTIVATE_SCALE,
    )


def find_artifact_popup_close(
    frame: np.ndarray,
    close_template: np.ndarray,
) -> Optional[TemplateMatch]:
    """Use the existing Lu Bu close icon to detect and close the popup."""
    if frame.ndim != 2 or frame.shape != (720, 640):
        return None
    x, y, score = find_template(
        frame,
        close_template,
        ARTIFACT_CLOSE_TEMPLATE_PATH.name,
        scales=ARTIFACT_CLOSE_SCALE,
    )
    if score < ARTIFACT_CLOSE_THRESHOLD:
        return None
    return x, y, score

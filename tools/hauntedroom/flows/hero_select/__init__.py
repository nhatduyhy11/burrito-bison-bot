"""Shared hero-select phase: single source for battle-ready detection."""

from hauntedroom.flows.hero_select.detection import (
    HEADER_TEMPLATE_PATH,
    HERO_SELECT_BATTLE_BUTTON_GEOMETRY,
    HERO_SELECT_BATTLE_BUTTON_REGION,
    HERO_SELECT_HEADER_REGION,
    HERO_SELECT_HEADER_SCALES,
    HERO_SELECT_HEADER_THRESHOLD,
    find_battle_button,
)

__all__ = [
    "HEADER_TEMPLATE_PATH",
    "HERO_SELECT_BATTLE_BUTTON_GEOMETRY",
    "HERO_SELECT_BATTLE_BUTTON_REGION",
    "HERO_SELECT_HEADER_REGION",
    "HERO_SELECT_HEADER_SCALES",
    "HERO_SELECT_HEADER_THRESHOLD",
    "find_battle_button",
]

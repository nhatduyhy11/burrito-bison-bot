"""Shared fixtures and helpers for hero-selection tests."""

import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
CAPTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures"
HERO_SELECT_FIXTURES_DIR = CAPTURES_DIR / "hero_select"
WRONG_FALLBACK_FIXTURES_DIR = CAPTURES_DIR / "wrong_fallback"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.flows.automap_support.hero_action import (  # noqa: E402
    choose_hero_levelup_option,
)
from hauntedroom.flows.automap_support.vision.hero_levelup import (  # noqa: E402
    HERO_LEVELUP_PRICE_REGION,
    HERO_LEVELUP_TEMPLATE_PATHS,
    load_hero_levelup_templates,
    prepare_hero_levelup_frame,
)


def load_hero_fixture(name: str) -> np.ndarray:
    image = cv2.imread(str(HERO_SELECT_FIXTURES_DIR / name))
    if image is None:
        raise AssertionError(f"Could not load hero-select fixture {name!r}")
    return image


def find_choice(frame_bgr: np.ndarray, template_paths=None):
    paths = HERO_LEVELUP_TEMPLATE_PATHS if template_paths is None else template_paths
    return choose_hero_levelup_option(
        paths,
        load_hero_levelup_templates(paths),
        prepare_hero_levelup_frame(frame_bgr),
    )


def make_levelup_available(image: np.ndarray) -> np.ndarray:
    x1, y1, _, _ = HERO_LEVELUP_PRICE_REGION
    image[y1 : y1 + 2, x1 : x1 + 4] = (255, 255, 255)
    return image

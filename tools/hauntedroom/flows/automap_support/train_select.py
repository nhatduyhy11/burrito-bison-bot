"""Detect and choose the two cards in the train-mode hero picker."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from hauntedroom.core.template_matching import load_template
from hauntedroom.flows.automap_support.vision.hero_levelup import (
    HERO_ASCEND_TEMPLATE_NAME,
    HERO_LEVELUP_TEMPLATE_PATHS,
)
from hauntedroom.flows.automap_support.vision.train import (
    TRAIN_ASCEND_TEMPLATE_THRESHOLD,
    TRAIN_TEMPLATE_THRESHOLD,
    find_train_cards,
    find_train_template_card,
)

TRAIN_CONFIRM_CLICK = (319, 670)
TRAIN_IGNORED_PRIORITY = 99.0


def _train_template_priority(path: Path) -> tuple[float, str]:
    """Parse the train selection priority encoded in an asset filename."""
    prefix = path.stem.split("_", 1)[0]
    try:
        priority = float(prefix)
    except ValueError:
        priority = float("inf")
    return priority, path.name


@dataclass(frozen=True)
class TrainChoice:
    x: int
    y: int
    confirm: bool = False
    template_name: Optional[str] = None
    score: Optional[float] = None


class TrainHeroMatcher:
    """Choose priority names first, then unselected purple cards left-to-right."""

    def __init__(
        self,
        template_paths: tuple[Path, ...] = HERO_LEVELUP_TEMPLATE_PATHS,
    ) -> None:
        self.templates = tuple(
            (path, load_template(path))
            for path in sorted(template_paths, key=_train_template_priority)
        )

    def find_choice(self, frame_bgr: np.ndarray) -> Optional[TrainChoice]:
        cards = find_train_cards(frame_bgr)
        if not cards:
            return None

        if sum(card.is_selected for card in cards) >= 2:
            return TrainChoice(*TRAIN_CONFIRM_CLICK, confirm=True)

        available = [card for card in cards if not card.is_selected]
        ignored_indices: set[int] = set()

        for template_path, template in self.templates:
            priority = _train_template_priority(template_path)[0]
            required_score = (
                TRAIN_ASCEND_TEMPLATE_THRESHOLD
                if template_path.name == HERO_ASCEND_TEMPLATE_NAME
                else TRAIN_TEMPLATE_THRESHOLD
            )
            match = find_train_template_card(
                frame_bgr,
                cards,
                template,
                template_path.name,
                required_score,
            )
            if match is None:
                continue
            card, score = match
            if priority >= TRAIN_IGNORED_PRIORITY:
                ignored_indices.add(card.index)
                continue
            if not card.is_selected:
                return TrainChoice(
                    card.x,
                    card.y,
                    template_name=template_path.name,
                    score=score,
                )

        purple = [
            card
            for card in available
            if card.is_purple and card.index not in ignored_indices
        ]
        if purple:
            card = purple[0]
            return TrainChoice(card.x, card.y)

        red = [
            card
            for card in available
            if not card.is_purple and card.index not in ignored_indices
        ]
        if red:
            card = red[0]
            return TrainChoice(card.x, card.y)

        return None

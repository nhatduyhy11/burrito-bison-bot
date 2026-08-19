"""Visual queries for the train-mode hero picker."""

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from hauntedroom.core.template_matching import find_template

# Train cards are rendered at four fixed columns in the 640x720 CSS viewport.
# The copied level-up name images are 1.25x larger than their train variants.
TRAIN_TEMPLATE_SCALE = 0.8
TRAIN_TEMPLATE_THRESHOLD = 0.58
TRAIN_ASCEND_TEMPLATE_THRESHOLD = 0.85
TRAIN_CARD_CENTERS = ((172, 566), (271, 566), (369, 566), (468, 566))
TRAIN_CARD_HALF_WIDTH = 44
TRAIN_CARD_TOP = 498
TRAIN_CARD_BOTTOM = 635

# One yellow top-left bracket is sufficient to tell whether a card is selected.
TRAIN_CORNER_TOP = 496
TRAIN_CORNER_BOTTOM = 512
TRAIN_CORNER_LEFT_OFFSET = -47
TRAIN_CORNER_RIGHT_OFFSET = -32
TRAIN_SELECTED_MIN_YELLOW_PIXELS = 8

# The solid left edge is stable even when the card artwork differs. Purple card
# edges have OpenCV HSV hue ~140; red card edges wrap around hue 0/180.
TRAIN_EDGE_TOP = 510
TRAIN_EDGE_BOTTOM = 625
TRAIN_EDGE_LEFT_OFFSET = -40
TRAIN_EDGE_RIGHT_OFFSET = -30
TRAIN_CARD_MIN_COLORED_PIXELS = 500
TRAIN_PURPLE_HUE_MIN = 125
TRAIN_PURPLE_HUE_MAX = 155


@dataclass(frozen=True)
class TrainCard:
    index: int
    x: int
    y: int
    is_purple: bool
    is_selected: bool


def _card_color_hue(frame_hsv: np.ndarray, x: int) -> Optional[float]:
    edge = frame_hsv[
        TRAIN_EDGE_TOP:TRAIN_EDGE_BOTTOM,
        x + TRAIN_EDGE_LEFT_OFFSET:x + TRAIN_EDGE_RIGHT_OFFSET,
    ]
    colored = (edge[:, :, 1] >= 60) & (edge[:, :, 2] >= 30)
    hues = edge[:, :, 0][colored]
    if hues.size < TRAIN_CARD_MIN_COLORED_PIXELS:
        return None
    return float(np.median(hues))


def _card_is_selected(frame_hsv: np.ndarray, x: int) -> bool:
    corner = frame_hsv[
        TRAIN_CORNER_TOP:TRAIN_CORNER_BOTTOM,
        x + TRAIN_CORNER_LEFT_OFFSET:x + TRAIN_CORNER_RIGHT_OFFSET,
    ]
    yellow = (
        (corner[:, :, 0] >= 15)
        & (corner[:, :, 0] <= 40)
        & (corner[:, :, 1] >= 120)
        & (corner[:, :, 2] >= 150)
    )
    return int(np.count_nonzero(yellow)) >= TRAIN_SELECTED_MIN_YELLOW_PIXELS


def find_train_cards(frame_bgr: np.ndarray) -> list[TrainCard]:
    """Return the four train cards, or [] when this is not its picker."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[:2] != (720, 640):
        return []

    frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    cards: list[TrainCard] = []
    for index, (x, y) in enumerate(TRAIN_CARD_CENTERS):
        hue = _card_color_hue(frame_hsv, x)
        if hue is None:
            return []
        is_purple = TRAIN_PURPLE_HUE_MIN <= hue <= TRAIN_PURPLE_HUE_MAX
        # A train card must be either purple or the red hue around 0/180. This
        # rejects ordinary battle frames before fixed coordinates are trusted.
        is_red = hue <= 12 or hue >= 165
        if not is_purple and not is_red:
            return []
        cards.append(
            TrainCard(
                index=index,
                x=x,
                y=y,
                is_purple=is_purple,
                is_selected=_card_is_selected(frame_hsv, x),
            )
        )
    return cards


def find_train_template_card(
    frame_bgr: np.ndarray,
    cards: list[TrainCard],
    template: np.ndarray,
    template_name: str,
    threshold: float,
) -> Optional[tuple[TrainCard, float]]:
    """Match one name template and map it to its nearest detected card."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3 or not cards:
        return None

    frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    name_region = frame_gray[TRAIN_CARD_TOP:TRAIN_CARD_BOTTOM, :]
    x, _local_y, score = find_template(
        name_region,
        template,
        template_name,
        scales=(TRAIN_TEMPLATE_SCALE,),
    )
    if score < threshold:
        return None

    card = min(cards, key=lambda candidate: abs(candidate.x - x))
    if abs(card.x - x) > TRAIN_CARD_HALF_WIDTH:
        return None
    return card, score

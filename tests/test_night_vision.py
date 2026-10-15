import sys
from pathlib import Path
from unittest import TestCase

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.flows.night import (  # noqa: E402
    find_night_accept_pair,
    find_night_challenge_button,
)
from hauntedroom.vision.night import (  # noqa: E402
    night_lobby_visible,
)
from hauntedroom.vision.victory import find_victory_panel  # noqa: E402


NIGHT_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "hauntedroom-captures" / "night"
TRAIN_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "train_flow"


def _load(path: Path):
    frame = cv2.imread(str(path))
    assert frame is not None
    return frame


class NightVisionTest(TestCase):
    def test_lobby_uses_crow_and_bottom_flame_from_full_capture(self):
        frame = _load(NIGHT_FIXTURES / "night-solo.png")

        self.assertTrue(night_lobby_visible(frame))
        self.assertEqual(find_night_challenge_button(frame).center, (320, 666))

    def test_accept_popup_reuses_red_yellow_pair_detector(self):
        pair = find_night_accept_pair(
            _load(NIGHT_FIXTURES / "night-solo-accept.png")
        )

        self.assertIsNotNone(pair)
        self.assertEqual(pair.red.center, (244, 464))
        self.assertEqual(pair.yellow.center, (394, 464))

    def test_shared_victory_detector_accepts_variable_reward_heights(self):
        cases = (
            (NIGHT_FIXTURES / "night-win.png", (235, 480)),
            (TRAIN_FIXTURES / "train_win.png", (278, 426)),
            (TRAIN_FIXTURES / "train_win_empty.png", (325, 394)),
        )
        for path, expected_bounds in cases:
            with self.subTest(path=path.name):
                panel = find_victory_panel(_load(path))
                self.assertIsNotNone(panel)
                self.assertEqual((panel.top, panel.bottom), expected_bounds)

    def test_shared_victory_detector_rejects_lobbies_and_popup(self):
        paths = (
            NIGHT_FIXTURES / "night-solo.png",
            NIGHT_FIXTURES / "night-solo-accept.png",
            TRAIN_FIXTURES / "train_available.png",
        )
        for path in paths:
            with self.subTest(path=path.name):
                self.assertIsNone(find_victory_panel(_load(path)))

import sys
from pathlib import Path
from unittest import TestCase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.template_matching import resolve_blocker_click


class BlockerClickResolutionTest(TestCase):
    def test_newbie_blocker_uses_fixed_top_left_click(self):
        self.assertEqual(
            resolve_blocker_click("overlay_newbie.png", 405, 506),
            (157, 54),
        )

    def test_other_blockers_keep_match_derived_click(self):
        self.assertEqual(
            resolve_blocker_click("overlay_close.png", 405, 506),
            (405, 506),
        )

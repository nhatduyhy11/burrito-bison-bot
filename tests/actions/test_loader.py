import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.actions.loader import load_actions
from hauntedroom.actions.models import (
    ClearBlockersAction,
    ClickAction,
    ClickTemplateAction,
    WaitAction,
)


class ActionLoaderTest(TestCase):
    def test_load_actions_returns_typed_normalized_actions(self):
        actions = load_actions(PROJECT_ROOT / "tools/hauntedroom_actions.sample.json")

        self.assertIsInstance(actions[0], ClearBlockersAction)
        self.assertIsInstance(actions[1], ClickTemplateAction)
        self.assertEqual(actions[1].type, "click_template")
        self.assertEqual(actions[1].template_path.name, "start_home.png")
        self.assertEqual(actions[1].delay_ms, 400)
        self.assertEqual(actions[1].template_scales, (1.0,))
        self.assertIsInstance(actions[-1], ClearBlockersAction)
        self.assertEqual(actions[-1].until_template_path.name, "start_home.png")

    def test_load_actions_supports_click_and_wait_actions(self):
        with TemporaryDirectory() as tmpdir:
            action_path = Path(tmpdir) / "actions.json"
            action_path.write_text(
                json.dumps(
                    [
                        {"type": "click", "x": "10", "y": 20, "note": "tap"},
                        {"type": "wait", "ms": 250},
                    ]
                ),
                encoding="utf-8",
            )

            actions = load_actions(action_path)

        self.assertEqual(actions, [ClickAction(10, 20, note="tap"), WaitAction(250)])

    def test_load_click_template_supports_search_region(self):
        with TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            (directory / "target.png").write_bytes(b"fixture")
            action_path = directory / "actions.json"
            action_path.write_text(
                json.dumps(
                    [
                        {
                            "type": "click_template",
                            "template": "target.png",
                            "region": [10, 20, 110, 220],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            actions = load_actions(action_path)

        self.assertEqual(actions[0].region, (10, 20, 110, 220))

    def test_load_click_template_rejects_invalid_search_region(self):
        with TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            (directory / "target.png").write_bytes(b"fixture")
            action_path = directory / "actions.json"
            action_path.write_text(
                json.dumps(
                    [
                        {
                            "type": "click_template",
                            "template": "target.png",
                            "region": [100, 20, 10, 220],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "increasing bounds"):
                load_actions(action_path)

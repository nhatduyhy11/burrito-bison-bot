import ast
from pathlib import Path
from unittest import TestCase


PACKAGE_DIR = Path(__file__).resolve().parents[1] / "tools" / "hauntedroom"


def internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return {module for module in modules if module.startswith("hauntedroom")}


class HauntedRoomDependencyTest(TestCase):
    def test_core_is_foundational(self):
        for path in (PACKAGE_DIR / "core").glob("*.py"):
            self.assertEqual(internal_imports(path), set(), path.name)

    def test_actions_do_not_depend_on_flows(self):
        for path in (PACKAGE_DIR / "actions").glob("*.py"):
            forbidden = {
                module
                for module in internal_imports(path)
                if module.startswith("hauntedroom.flows")
            }
            self.assertEqual(forbidden, set(), path.name)

    def test_control_events_only_depend_on_core_or_sibling_modules(self):
        for path in (PACKAGE_DIR / "control_events").glob("*.py"):
            forbidden = {
                module
                for module in internal_imports(path)
                if not module.startswith(
                    ("hauntedroom.core", "hauntedroom.control_events")
                )
            }
            self.assertEqual(forbidden, set(), path.name)

    def test_flows_are_independent_from_actions_and_each_other(self):
        allowed_support_imports = {
            "automap.py": {
                "hauntedroom.flows.automap_support.boss_action",
                "hauntedroom.flows.automap_support.hero_levelup",
                "hauntedroom.flows.automap_support.detectors",
            },
        }
        for path in (PACKAGE_DIR / "flows").glob("*.py"):
            forbidden = {
                module
                for module in internal_imports(path)
                if module.startswith(("hauntedroom.actions", "hauntedroom.flows"))
                and module not in allowed_support_imports.get(path.name, set())
            }
            self.assertEqual(forbidden, set(), path.name)

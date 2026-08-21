import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, call, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.runner.reload import get_automap_flow


class ReloadPolicyTest(TestCase):
    @patch("hauntedroom.runner.reload.reload_action_modules")
    @patch("hauntedroom.runner.reload.importlib.reload")
    def test_dev_reload_refreshes_support_modules_before_automap(
        self, reload_module, reload_action_modules
    ):
        from hauntedroom import settings
        from hauntedroom.flows import automap
        from hauntedroom.flows.automap_support import (
            boss_action,
            boss_flow,
            gear_action,
            hero_action,
            upgrade_action,
        )
        from hauntedroom.flows.automap_support import (
            flow as automap_flow_support,
        )
        from hauntedroom.flows.automap_support.map import (
            blocker,
            first_win,
            lifecycle,
            model_state,
            reward,
        )
        from hauntedroom.flows.automap_support.vision import (
            boss_controls as boss_controls_vision,
        )
        from hauntedroom.flows.automap_support.vision import (
            boss_hp as boss_hp_vision,
        )
        from hauntedroom.flows.automap_support.vision import (
            boss_progress as boss_progress_vision,
        )
        from hauntedroom.flows.automap_support.vision import (
            build as build_vision,
        )
        from hauntedroom.flows.automap_support.vision import (
            gear as gear_vision,
        )
        from hauntedroom.flows.automap_support.vision import (
            hero_levelup as hero_levelup_vision,
        )

        refreshed_flow = Mock()
        refreshed_automap = Mock(run_automap_flow=refreshed_flow)
        reload_module.side_effect = [
            settings,
            boss_controls_vision,
            boss_hp_vision,
            boss_progress_vision,
            build_vision,
            gear_vision,
            hero_levelup_vision,
            boss_action,
            gear_action,
            model_state,
            first_win,
            reward,
            blocker,
            lifecycle,
            upgrade_action,
            hero_action,
            boss_flow,
            automap_flow_support,
            refreshed_automap,
        ]

        result = get_automap_flow(dev_reload=True)

        self.assertIs(result, refreshed_flow)
        reload_action_modules.assert_called_once_with()
        self.assertEqual(
            reload_module.call_args_list,
            [
                call(settings),
                call(boss_controls_vision),
                call(boss_hp_vision),
                call(boss_progress_vision),
                call(build_vision),
                call(gear_vision),
                call(hero_levelup_vision),
                call(boss_action),
                call(gear_action),
                call(model_state),
                call(first_win),
                call(reward),
                call(blocker),
                call(lifecycle),
                call(upgrade_action),
                call(hero_action),
                call(boss_flow),
                call(automap_flow_support),
                call(automap),
            ],
        )

    @patch("hauntedroom.runner.reload.importlib.reload")
    def test_action_reload_refreshes_action_loader_and_runner(self, reload_module):
        from hauntedroom.actions import loader as actions_loader
        from hauntedroom.actions import runner as actions_runner
        from hauntedroom.control_events import blockers as control_blockers
        from hauntedroom.control_events import new_tab_blocker
        from hauntedroom.core import template_detection, template_matching, vision
        from hauntedroom.runner import reload as reload_policy

        refreshed_load_actions = Mock()
        refreshed_run_actions = Mock()
        refreshed_loader = Mock(load_actions=refreshed_load_actions)
        refreshed_runner = Mock(run_actions=refreshed_run_actions)
        reload_module.side_effect = [
            template_matching,
            vision,
            template_detection,
            new_tab_blocker,
            control_blockers,
            refreshed_loader,
            refreshed_runner,
        ]
        original_load_actions = reload_policy.load_actions
        original_run_actions = reload_policy.run_actions

        try:
            result = reload_policy.reload_action_modules()
            observed_load_actions = reload_policy.load_actions
            observed_run_actions = reload_policy.run_actions
        finally:
            reload_policy.load_actions = original_load_actions
            reload_policy.run_actions = original_run_actions

        self.assertIs(result, refreshed_run_actions)
        self.assertIs(observed_load_actions, refreshed_load_actions)
        self.assertIs(observed_run_actions, refreshed_run_actions)
        self.assertEqual(
            reload_module.call_args_list,
            [
                call(template_matching),
                call(vision),
                call(template_detection),
                call(new_tab_blocker),
                call(control_blockers),
                call(actions_loader),
                call(actions_runner),
            ],
        )

    @patch("hauntedroom.runner.reload.importlib.reload", side_effect=AssertionError)
    def test_normal_mode_does_not_reload(self, _reload_module):
        from hauntedroom.flows import automap

        self.assertIs(get_automap_flow(), automap.run_automap_flow)

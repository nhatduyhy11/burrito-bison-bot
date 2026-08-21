import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.runtime import FlowControl
from hauntedroom.runner.default_commands import FLOW_COMMANDS, SCREEN_FLOW_COMMANDS
from hauntedroom.runner.standby import (
    format_start_auto_control_guide,
    format_start_auto_hotkeys,
    handle_control_command,
    validate_start_auto_hotkeys,
)
from hauntedroom.screen_detect import ScreenName

VALID_HOTKEYS = {
    "pause_resume": "1",
    "pause_at_boss": "2",
    "pause_at_final_boss": "3",
    "screenshot": "8",
    "stop": "0",
}


class StandbyHotkeysTest(IsolatedAsyncioTestCase):
    def test_start_auto_hotkeys_format_each_control_on_its_own_line(self):
        self.assertEqual(
            format_start_auto_hotkeys(VALID_HOTKEYS),
            "    Shift+1 pause/resume\n"
            "    Shift+2 pause at boss\n"
            "    Shift+3 pause at final boss\n"
            "    Shift+8 screenshot\n"
            "    Shift+0 stop",
        )

    def test_start_auto_control_guide_formats_each_control_on_its_own_line(self):
        self.assertEqual(
            format_start_auto_control_guide(VALID_HOTKEYS),
            "Auto-map controls:\n"
            "  Shift+1 pause/resume\n"
            "  Shift+2 pause at boss\n"
            "  Shift+3 pause at final boss\n"
            "  Shift+8 screenshot\n"
            "  Shift+0 stop",
        )

    async def test_automap_hotkeys_arm_boss_pauses_for_shift_2_and_shift_3(self):
        for current_command in (
            SCREEN_FLOW_COMMANDS[ScreenName.AUTOMAP],
            SCREEN_FLOW_COMMANDS[ScreenName.HOME],
        ):
            with self.subTest(current_command=current_command.name):
                control = FlowControl()
                page = Mock()
                flow_task = Mock()

                self.assertTrue(
                    await handle_control_command(
                        "2", page, flow_task, control, current_command
                    )
                )
                self.assertEqual(
                    control.boss_pause_target,
                    FlowControl.PAUSE_AT_ANY_BOSS,
                )

                self.assertTrue(
                    await handle_control_command(
                        "3", page, flow_task, control, current_command
                    )
                )
                self.assertEqual(
                    control.boss_pause_target,
                    FlowControl.PAUSE_AT_FINAL_BOSS,
                )

                self.assertTrue(
                    await handle_control_command(
                        "7", page, flow_task, control, current_command
                    )
                )
                self.assertEqual(
                    control.boss_pause_target,
                    FlowControl.PAUSE_AT_FINAL_BOSS,
                )

    async def test_automap_hotkeys_ignore_other_flows(self):
        control = FlowControl()

        self.assertFalse(
            await handle_control_command(
                "2", Mock(), Mock(), control, FLOW_COMMANDS["5"]
            )
        )
        self.assertIsNone(control.boss_pause_target)

    async def test_automap_hotkeys_can_be_remapped_by_config_values(self):
        remapped = {
            "pause_resume": "4",
            "pause_at_boss": "5",
            "pause_at_final_boss": "6",
            "stop": "7",
            "screenshot": "9",
        }

        for current_command in (
            SCREEN_FLOW_COMMANDS[ScreenName.AUTOMAP],
            SCREEN_FLOW_COMMANDS[ScreenName.HOME],
        ):
            with self.subTest(current_command=current_command.name):
                control = Mock()
                control.pause_at_next_boss.return_value = True

                self.assertTrue(
                    await handle_control_command(
                        "5",
                        Mock(),
                        Mock(),
                        control,
                        current_command,
                        remapped,
                    )
                )
                control.pause_at_next_boss.assert_called_once_with(final_only=False)

                # The old default is unmapped and must not invoke any control action.
                self.assertTrue(
                    await handle_control_command(
                        "2",
                        Mock(),
                        Mock(),
                        control,
                        current_command,
                        remapped,
                    )
                )
                control.pause_at_next_boss.assert_called_once_with(final_only=False)
                control.pause.assert_not_called()
                control.resume.assert_not_called()
                control.set.assert_not_called()

    def test_start_auto_hotkey_config_rejects_duplicate_digits(self):
        duplicate_hotkeys = {**VALID_HOTKEYS, "pause_at_boss": "1"}

        with self.assertRaisesRegex(ValueError, "cannot assign one digit twice"):
            validate_start_auto_hotkeys(duplicate_hotkeys)

    def test_start_auto_hotkey_config_rejects_missing_or_unknown_actions(self):
        invalid_hotkeys = dict(VALID_HOTKEYS)
        del invalid_hotkeys["screenshot"]
        invalid_hotkeys["capture"] = "8"

        with self.assertRaisesRegex(
            ValueError,
            r"missing=\['screenshot'\], unknown=\['capture'\]",
        ):
            validate_start_auto_hotkeys(invalid_hotkeys)

    def test_start_auto_hotkey_config_rejects_non_digit_values(self):
        invalid_hotkeys = {**VALID_HOTKEYS, "stop": "t"}

        with self.assertRaisesRegex(ValueError, r"invalid=\['t'\]"):
            validate_start_auto_hotkeys(invalid_hotkeys)

    def test_start_auto_hotkey_validation_returns_an_independent_copy(self):
        configured_hotkeys = dict(VALID_HOTKEYS)

        validated = validate_start_auto_hotkeys(configured_hotkeys)
        configured_hotkeys["stop"] = "9"

        self.assertEqual(validated, VALID_HOTKEYS)

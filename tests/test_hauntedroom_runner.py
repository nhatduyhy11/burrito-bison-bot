import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import cv2
import numpy as np

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from hauntedroom.actions.runner import (
    SKIP_TEMPLATE_MATCHED,
    run_actions,
    wait_for_template,
)
from hauntedroom.core.runtime import HOTKEY_SCRIPT, start_hotkey_listener
from hauntedroom.flows.automap import (
    AUTOMAP_POLL_MS,
    AutomapConfig,
    AutomapFlow,
    BOSS_HP_TEMPLATE_PATH,
    LV_SPIN_CLICK_OFFSET_X,
    MAP_END_CHECK_INTERVAL_SEC,
    MAP_END_TEMPLATE_THRESHOLD,
    PROTECT_CLICK,
    PROTECT_CONFIRM_CLICK,
    UPGRADE_CONFIRM_CLICK,
    run_automap_flow,
)
from hauntedroom.flows.boss_action import (
    PET_ACTION_POSITION,
    PET_READY_TEMPLATE_PATH,
    SPELL_ACTION_POSITION,
    SPELL_READY_TEMPLATE_PATH,
    activate_boss_spell,
    deploy_boss_pet,
)
from hauntedroom.flows.research import run_research_flow
from hauntedroom.flows.map_vision_helper import (
    BOSS_CRITICAL_REGION,
    PET_READY_REGION,
    PROTECT_AVAILABLE_REGION,
    SPELL_READY_REGION,
    boss_action_has_ready_glow,
    find_boss_health_bar,
    find_first_available_build_option,
    region_has_enough_white,
)
from hauntedroom_runner import get_automap_flow, run_standby_controller


class HauntedRoomRunnerTimeoutTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()

        self.template_path = Path("start.png")
        self.actions = [
            {
                "type": "click_template",
                "_template_path": self.template_path,
                "note": "Start",
                "delay_ms": 0,
            },
            {"type": "click", "x": 10, "y": 20},
        ]

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
    async def test_first_timeout_skips_rest_of_loop_then_retries(
        self, wait_for_template, _load_template
    ):
        wait_for_template.side_effect = [
            TimeoutError("first timeout"),
            (30, 40, 0.95),
        ]

        await run_actions(self.page, self.actions, loop_count=2)

        self.assertEqual(wait_for_template.await_count, 2)
        self.assertEqual(self.page.mouse.click.await_count, 2)

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
    async def test_second_timeout_stops_runner(
        self, wait_for_template, _load_template
    ):
        wait_for_template.side_effect = [
            TimeoutError("first timeout"),
            TimeoutError("second timeout"),
        ]

        with self.assertRaisesRegex(TimeoutError, "second timeout"):
            await run_actions(self.page, self.actions, loop_count=3)

        self.assertEqual(wait_for_template.await_count, 2)
        self.page.mouse.click.assert_not_awaited()

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
    async def test_successful_loop_resets_timeout_count(
        self, wait_for_template, _load_template
    ):
        wait_for_template.side_effect = [
            TimeoutError("first timeout"),
            (30, 40, 0.95),
            TimeoutError("timeout after recovery"),
            TimeoutError("consecutive timeout"),
        ]

        with self.assertRaisesRegex(TimeoutError, "consecutive timeout"):
            await run_actions(self.page, self.actions, loop_count=4)

        self.assertEqual(wait_for_template.await_count, 4)
        self.assertEqual(self.page.mouse.click.await_count, 2)

    @patch(
        "hauntedroom.actions.runner.load_template",
        return_value=np.zeros((1, 1), dtype=np.uint8),
    )
    @patch("hauntedroom.actions.runner.wait_for_template", new_callable=AsyncMock)
    async def test_click_template_skip_if_template_avoids_clicking_stale_step(
        self, wait_for_template, load_template
    ):
        skip_path = Path("home.png")
        self.actions[0]["_skip_if_template_path"] = skip_path
        wait_for_template.return_value = SKIP_TEMPLATE_MATCHED

        await run_actions(self.page, self.actions, loop_count=1)

        self.assertEqual(load_template.call_count, 2)
        wait_for_template.assert_awaited_once()
        self.assertIs(wait_for_template.await_args.args[-2], load_template.return_value)
        self.assertEqual(wait_for_template.await_args.args[-1], skip_path.name)
        self.page.mouse.click.assert_awaited_once_with(10, 20, button="left")

    @patch(
        "hauntedroom.actions.runner.capture_page_grayscale",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.actions.runner.find_template")
    async def test_wait_for_template_returns_skip_when_skip_template_matches(
        self, find_template, capture_page_grayscale
    ):
        capture_page_grayscale.return_value = np.zeros((10, 10), dtype=np.uint8)
        find_template.side_effect = [(0, 0, 0.4), (20, 30, 0.95)]

        result = await wait_for_template(
            self.page,
            np.zeros((1, 1), dtype=np.uint8),
            "exit_back.png",
            0.75,
            1000,
            400,
            skip_template=np.zeros((1, 1), dtype=np.uint8),
            skip_template_name="start_home.png",
        )

        self.assertIs(result, SKIP_TEMPLATE_MATCHED)
        self.page.wait_for_timeout.assert_not_awaited()


class HauntedRoomRunnerHotkeyTest(IsolatedAsyncioTestCase):
    @patch("hauntedroom_runner.importlib.reload")
    @patch("hauntedroom_runner.importlib.invalidate_caches")
    def test_dev_reload_refreshes_vision_before_automap(
        self, invalidate_caches, reload_module
    ):
        from hauntedroom.core import vision
        from hauntedroom.flows import automap, boss_action, map_vision_helper

        refreshed_flow = Mock()
        refreshed_automap = Mock(run_automap_flow=refreshed_flow)
        reload_module.side_effect = [
            vision,
            map_vision_helper,
            boss_action,
            refreshed_automap,
        ]

        result = get_automap_flow(dev_reload=True)

        self.assertIs(result, refreshed_flow)
        invalidate_caches.assert_called_once_with()
        self.assertEqual(
            reload_module.call_args_list,
            [
                call(vision),
                call(map_vision_helper),
                call(boss_action),
                call(automap),
            ],
        )

    @patch("hauntedroom_runner.importlib.reload", side_effect=AssertionError)
    def test_normal_mode_does_not_reload(self, _reload_module):
        from hauntedroom.flows import automap

        self.assertIs(get_automap_flow(), automap.run_automap_flow)

    def test_hotkey_script_accepts_shift_8(self):
        self.assertIn("!/^Digit[0-9]$/.test(event.code)", HOTKEY_SCRIPT)

    @patch("hauntedroom_runner.save_live_screenshot", new_callable=AsyncMock)
    @patch("hauntedroom_runner.start_hotkey_listener", new_callable=AsyncMock)
    async def test_shift_8_saves_live_screenshot_and_stays_idle(
        self,
        start_hotkey_listener,
        save_live_screenshot,
    ):
        page = Mock()

        async def enqueue_capture(_page, command_queue):
            command_queue.put_nowait("8")

        async def stop_after_capture(_page):
            raise RuntimeError("stop test loop")

        start_hotkey_listener.side_effect = enqueue_capture
        save_live_screenshot.side_effect = stop_after_capture

        with self.assertRaisesRegex(RuntimeError, "stop test loop"):
            await run_standby_controller(page, [], dev_reload=False)

        save_live_screenshot.assert_awaited_once_with(page)

    async def test_stop_event_ends_flow_without_clicking(self):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        stop_event = asyncio.Event()
        stop_event.set()

        completed = await run_actions(
            page,
            [{"type": "click", "x": 10, "y": 20}],
            loop_count=None,
            stop_event=stop_event,
        )

        self.assertFalse(completed)
        page.mouse.click.assert_not_awaited()


class HauntedRoomAutoMapTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.evaluate = AsyncMock()
        self.page.wait_for_timeout = AsyncMock()
        self.page.mouse = Mock()
        self.page.mouse.click = AsyncMock()
        self.page.mouse.move = AsyncMock()
        self.page.mouse.down = AsyncMock()
        self.page.mouse.up = AsyncMock()

    @staticmethod
    def make_protect_available(image):
        x1, y1, _, _ = PROTECT_AVAILABLE_REGION
        image[y1 : y1 + 2, x1 : x1 + 4] = (255, 255, 255)
        return image

    def test_region_requires_enough_white_inside_configured_rectangle(self):
        image = np.zeros((720, 640, 3), dtype=np.uint8)
        x1, y1, _, _ = PROTECT_AVAILABLE_REGION
        image[y1 : y1 + 2, x1 : x1 + 3] = (255, 255, 255)
        self.assertFalse(region_has_enough_white(image))

        image[y1 : y1 + 2, x1 : x1 + 4] = (255, 255, 255)
        self.assertTrue(region_has_enough_white(image))

    def test_region_does_not_treat_gold_as_white(self):
        image = np.zeros((720, 640, 3), dtype=np.uint8)
        x1, y1, x2, y2 = PROTECT_AVAILABLE_REGION
        image[y1:y2, x1:x2] = (40, 180, 245)

        self.assertFalse(region_has_enough_white(image))

    def test_region_outside_image_fails_closed(self):
        image = np.full((100, 100, 3), 255, dtype=np.uint8)

        self.assertFalse(region_has_enough_white(image))

    def test_available_and_unavailable_reference_colors(self):
        misc_dir = TOOLS_DIR / "rooms" / "misc"
        available = cv2.imread(str(misc_dir / "white_available.png"))
        unavailable = cv2.imread(str(misc_dir / "red_unavailable.png"))

        self.assertTrue(
            region_has_enough_white(available, region=(90, 8, 140, 30))
        )
        self.assertFalse(
            region_has_enough_white(unavailable, region=(90, 8, 140, 30))
        )

    def test_finds_boss_sized_hp_bar_in_critical_region_without_color(self):
        template = cv2.imread(str(BOSS_HP_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(template)
        frame = np.full((720, 640), 80, dtype=np.uint8)
        x, y = 220, 300
        height, width = template.shape
        # Inversion changes every source color/intensity while preserving the
        # narrow vertical stripe geometry used by the detector.
        frame[y : y + height, x : x + width] = 255 - template

        match = find_boss_health_bar(frame, template)

        self.assertIsNotNone(match)
        match_x, match_y, score = match
        self.assertEqual((match_x, match_y), (x + width // 2, y + height // 2))
        self.assertGreaterEqual(score, 0.85)

    def test_rejects_miniboss_sized_hp_bar(self):
        template = cv2.imread(str(BOSS_HP_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
        frame = np.full((720, 640), 80, dtype=np.uint8)
        mini = cv2.resize(template, (40, template.shape[0]), interpolation=cv2.INTER_AREA)
        frame[300 : 300 + mini.shape[0], 220 : 220 + mini.shape[1]] = mini

        self.assertIsNone(find_boss_health_bar(frame, template))

    def test_rejects_boss_bar_outside_critical_region(self):
        template = cv2.imread(str(BOSS_HP_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
        frame = np.full((720, 640), 80, dtype=np.uint8)
        height, width = template.shape
        x = BOSS_CRITICAL_REGION[0] - width
        y = BOSS_CRITICAL_REGION[1]
        frame[y : y + height, x : x + width] = template

        self.assertIsNone(find_boss_health_bar(frame, template))

    def test_ready_glow_detector_accepts_supplied_live_capture(self):
        capture = cv2.imread(
            str(
                TOOLS_DIR.parent
                / ".tmp"
                / "hauntedroom-captures"
                / "pet-spell-ready.png"
            )
        )
        pet_reference = cv2.imread(str(PET_READY_TEMPLATE_PATH))
        spell_reference = cv2.imread(str(SPELL_READY_TEMPLATE_PATH))

        self.assertIsNotNone(capture)
        self.assertTrue(
            boss_action_has_ready_glow(
                capture,
                pet_reference,
                PET_READY_REGION,
            )
        )
        self.assertTrue(
            boss_action_has_ready_glow(
                capture,
                spell_reference,
                SPELL_READY_REGION,
            )
        )

    def test_ready_glow_detector_ignores_exact_glow_shape(self):
        reference = np.zeros((20, 20, 3), dtype=np.uint8)
        reference[2:10, 2:10] = (0, 220, 255)
        frame = np.zeros((40, 40, 3), dtype=np.uint8)
        frame[20:24, 10:26] = (0, 220, 255)

        self.assertTrue(
            boss_action_has_ready_glow(frame, reference, (0, 10, 30, 30))
        )
        self.assertFalse(
            boss_action_has_ready_glow(
                np.zeros_like(frame),
                reference,
                (0, 10, 30, 30),
            )
        )

    @patch("hauntedroom.flows.boss_action.capture_page_bgr", new_callable=AsyncMock)
    async def test_activate_boss_spell_clicks_ready_spell_then_boss(
        self,
        capture_page_bgr,
    ):
        capture_page_bgr.return_value = cv2.imread(
            str(
                TOOLS_DIR.parent
                / ".tmp"
                / "hauntedroom-captures"
                / "pet-spell-ready.png"
            )
        )
        boss_position = (250, 300)

        activated = await activate_boss_spell(self.page, boss_position)

        self.assertTrue(activated)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*SPELL_ACTION_POSITION), call(*boss_position)],
        )

    @patch("hauntedroom.flows.boss_action.capture_page_bgr", new_callable=AsyncMock)
    async def test_deploy_boss_pet_drags_ready_pet_to_boss(
        self,
        capture_page_bgr,
    ):
        capture_page_bgr.return_value = cv2.imread(
            str(
                TOOLS_DIR.parent
                / ".tmp"
                / "hauntedroom-captures"
                / "pet-spell-ready.png"
            )
        )
        boss_position = (250, 300)

        deployed = await deploy_boss_pet(self.page, boss_position)

        self.assertTrue(deployed)
        self.page.mouse.move.assert_has_awaits(
            [call(*PET_ACTION_POSITION), call(*boss_position, steps=10)]
        )
        self.page.mouse.down.assert_awaited_once_with()
        self.page.mouse.up.assert_awaited_once_with()

    @patch("hauntedroom.flows.automap.load_template")
    async def test_automap_flow_loads_all_templates_once_per_run(self, load_template):
        load_template.return_value = np.zeros((2, 2), dtype=np.uint8)

        AutomapFlow(self.page, asyncio.Event(), AutomapConfig())

        self.assertEqual(load_template.call_count, 8)

    @patch(
        "hauntedroom.flows.automap.find_boss_health_bar",
        return_value=(250, 300, 0.90),
    )
    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.automap.find_template",
        side_effect=[
            (0, 0, 0.0),
            (0, 0, 0.0),
            (612, 35, 0.95),
        ],
    )
    @patch("hauntedroom.flows.automap.find_template_matches", return_value=[])
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_boss_in_critical_region_clicks_exit_once_then_stops(
        self,
        capture_page_bgr,
        _find_template_matches,
        _find_template,
        _load_template,
        _find_boss_health_bar,
    ):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        stop_event = asyncio.Event()

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        capture_page_bgr.assert_awaited_once_with(self.page)
        self.page.mouse.click.assert_awaited_once_with(612, 35)

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template", return_value=(0, 0, 0.0))
    @patch("hauntedroom.flows.automap.find_template_matches", return_value=[])
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_available_protect_gate_clicks_twice_then_stops(
        self,
        capture_page_bgr,
        _find_template_matches,
        _find_template,
        _load_template,
    ):
        capture_page_bgr.return_value = self.make_protect_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )
        stop_event = asyncio.Event()

        async def stop_after_second_click(*_args, **_kwargs):
            if self.page.mouse.click.await_count == 2:
                stop_event.set()

        self.page.mouse.click.side_effect = stop_after_second_click

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(*PROTECT_CLICK), call(*PROTECT_CONFIRM_CLICK)],
        )
        self.assertEqual(
            self.page.wait_for_timeout.await_args_list,
            [call(250), call(250), call(250), call(50)],
        )

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template", return_value=(200, 20, 0.92))
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_level_spin_interrupt_clicks_left_offset_before_protect_gate(
        self,
        capture_page_bgr,
        find_template_matches,
        _find_template,
        _load_template,
    ):
        capture_page_bgr.return_value = self.make_protect_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )
        find_template_matches.return_value = []
        stop_event = asyncio.Event()

        async def stop_after_first_click(*_args, **_kwargs):
            stop_event.set()

        self.page.mouse.click.side_effect = stop_after_first_click

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.page.mouse.click.assert_awaited_once_with(
            max(0, 200 + LV_SPIN_CLICK_OFFSET_X),
            560,
        )
        self.page.wait_for_timeout.assert_awaited_once_with(AUTOMAP_POLL_MS)

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.automap.find_template",
        side_effect=[(0, 0, 0.0), (0, 0, 0.0), (200, 20, 0.92)],
    )
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_level_up_rechecks_level_spin_before_confirm_click(
        self,
        capture_page_bgr,
        find_template_matches,
        _find_template,
        _load_template,
    ):
        capture_page_bgr.side_effect = [
            np.zeros((720, 640, 3), dtype=np.uint8),
            np.zeros((720, 640, 3), dtype=np.uint8),
        ]
        find_template_matches.side_effect = [
            [(120, 500, 0.91)],
        ]
        stop_event = asyncio.Event()

        async def stop_after_level_spin_click(*_args, **_kwargs):
            if self.page.mouse.click.await_count == 2:
                stop_event.set()

        self.page.mouse.click.side_effect = stop_after_level_spin_click

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(120, 500),
                call(max(0, 200 + LV_SPIN_CLICK_OFFSET_X), 560),
            ],
        )

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.automap.find_template",
        side_effect=[
            (0, 0, 0.0),
            (300, 400, 0.91),
            (50, 600, 0.95),
        ],
    )
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_clicks_reward_first_match_then_completes_at_home(
        self,
        capture_page_bgr,
        find_template_matches,
        find_template,
        _load_template,
    ):
        capture_page_bgr.return_value = self.make_protect_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )
        find_template_matches.return_value = [
            (305, 466, 1.0),
            (341, 466, 0.98),
        ]

        completed = await run_automap_flow(self.page, asyncio.Event())

        self.assertTrue(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(300, 400),
                call(305, 466),
            ],
        )
        self.assertEqual(find_template.call_args_list[1].args[2], "map_end.png")
        reward_call = find_template_matches.call_args_list[0]
        self.assertEqual(reward_call.args[2], "win_reward.png")
        self.assertEqual(reward_call.kwargs["threshold"], 0.90)

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.automap.find_template",
        side_effect=[
            (0, 0, 0.0),
            (300, 400, 0.91),
            (50, 600, 0.95),
        ],
    )
    @patch("hauntedroom.flows.automap.find_template_matches", return_value=[])
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_completes_when_home_ready_without_reward(
        self,
        capture_page_bgr,
        find_template_matches,
        find_template,
        _load_template,
    ):
        capture_page_bgr.return_value = self.make_protect_available(
            np.zeros((720, 640, 3), dtype=np.uint8)
        )

        completed = await run_automap_flow(self.page, asyncio.Event())

        self.assertTrue(completed)
        self.page.mouse.click.assert_awaited_once_with(300, 400)
        self.assertEqual(find_template.call_args_list[1].args[2], "map_end.png")
        find_template_matches.assert_called_once()

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template", return_value=(0, 0, 0.0))
    @patch("hauntedroom.flows.automap.find_template_matches", return_value=[])
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_map_end_is_checked_at_most_once_per_interval(
        self,
        capture_page_bgr,
        find_template_matches,
        find_template,
        _load_template,
    ):
        capture_page_bgr.return_value = np.zeros((720, 640, 3), dtype=np.uint8)
        stop_event = asyncio.Event()

        async def stop_after_second_poll(*_args, **_kwargs):
            if self.page.wait_for_timeout.await_count == 2:
                stop_event.set()

        self.page.wait_for_timeout.side_effect = stop_after_second_poll

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.assertGreater(MAP_END_CHECK_INTERVAL_SEC, AUTOMAP_POLL_MS / 1000)
        self.assertGreater(MAP_END_TEMPLATE_THRESHOLD, 0.80)
        self.assertEqual(
            [
                call_args.args[2]
                for call_args in find_template.call_args_list
                if call_args.args[2] == "map_end.png"
            ],
            ["map_end.png"],
        )
        matched_template_names = [
            call_args.args[2]
            for call_args in find_template_matches.call_args_list
        ]
        self.assertEqual(matched_template_names.count("lv_up.png"), 2)
        self.assertEqual(matched_template_names.count("built.png"), 2)

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template", return_value=(0, 0, 0.0))
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_level_up_uses_largest_y_and_rechecks_before_confirm(
        self,
        capture_page_bgr,
        find_template_matches,
        _find_template,
        _load_template,
    ):
        unavailable = np.zeros((720, 640, 3), dtype=np.uint8)
        available = self.make_protect_available(np.zeros_like(unavailable))
        capture_page_bgr.side_effect = [unavailable, unavailable, available]
        find_template_matches.return_value = [
            (100, 200, 0.99),
            (120, 500, 0.91),
        ]
        stop_event = asyncio.Event()

        async def stop_after_protect_clicks(*_args, **_kwargs):
            if self.page.mouse.click.await_count == 4:
                stop_event.set()

        self.page.mouse.click.side_effect = stop_after_protect_clicks

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [
                call(120, 500),
                call(*UPGRADE_CONFIRM_CLICK),
                call(*PROTECT_CLICK),
                call(*PROTECT_CONFIRM_CLICK),
            ],
        )
        self.assertEqual(capture_page_bgr.await_count, 3)
        level_up_call = find_template_matches.call_args_list[0]
        matched_frame = level_up_call.args[0]
        self.assertEqual(matched_frame.shape, (720, 640))
        self.assertEqual(
            level_up_call.kwargs["threshold"],
            0.80,
        )

    @staticmethod
    def make_build_button(
        popup: np.ndarray,
        top: int,
        price_color: tuple[int, int, int],
    ) -> tuple[int, int]:
        left, width, height = 392, 78, 26
        popup[top : top + height, left : left + width] = (90, 215, 252)
        popup[top + 8 : top + 10, left + 48 : left + 58] = price_color
        return left + width // 2, top + height // 2

    def test_single_centered_white_build_option_is_available(self):
        popup = np.zeros((720, 640, 3), dtype=np.uint8)
        expected_click = self.make_build_button(popup, 361, (255, 255, 255))

        self.assertEqual(
            find_first_available_build_option(popup),
            expected_click,
        )

    def test_red_first_build_option_skips_to_white_second_option(self):
        popup = np.zeros((720, 640, 3), dtype=np.uint8)
        self.make_build_button(popup, 329, (0, 0, 255))
        expected_click = self.make_build_button(popup, 394, (255, 255, 255))

        self.assertEqual(
            find_first_available_build_option(popup),
            expected_click,
        )

    @patch(
        "hauntedroom.flows.automap.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch("hauntedroom.flows.automap.find_template", return_value=(0, 0, 0.0))
    @patch("hauntedroom.flows.automap.find_template_matches")
    @patch("hauntedroom.flows.automap.capture_page_bgr", new_callable=AsyncMock)
    async def test_build_uses_highest_x_then_y_and_first_white_option(
        self,
        capture_page_bgr,
        find_template_matches,
        _find_template,
        _load_template,
    ):
        initial = np.zeros((720, 640, 3), dtype=np.uint8)
        popup = np.zeros_like(initial)
        option_click = self.make_build_button(popup, 361, (255, 255, 255))
        capture_page_bgr.side_effect = [initial, popup]

        def matches_for(_frame, _template, template_name, **_kwargs):
            if template_name == "built.png":
                return [
                    (300, 600, 0.95),
                    (500, 300, 0.91),
                    (500, 600, 0.90),
                ]
            return []

        find_template_matches.side_effect = matches_for
        stop_event = asyncio.Event()

        async def stop_after_option_click(*_args, **_kwargs):
            if self.page.mouse.click.await_count == 2:
                stop_event.set()

        self.page.mouse.click.side_effect = stop_after_option_click

        completed = await run_automap_flow(self.page, stop_event)

        self.assertFalse(completed)
        self.assertEqual(
            self.page.mouse.click.await_args_list,
            [call(500, 600), call(*option_click)],
        )

    async def test_hotkey_listener_is_installed_for_current_and_future_frames(self):
        page = Mock()
        page.expose_binding = AsyncMock()
        page.add_init_script = AsyncMock()
        frame_one = Mock()
        frame_one.evaluate = AsyncMock()
        frame_two = Mock()
        frame_two.evaluate = AsyncMock()
        page.frames = [frame_one, frame_two]

        await start_hotkey_listener(page, asyncio.Queue())

        page.expose_binding.assert_awaited_once()
        page.add_init_script.assert_awaited_once_with(HOTKEY_SCRIPT)
        frame_one.evaluate.assert_awaited_once_with(HOTKEY_SCRIPT)
        frame_two.evaluate.assert_awaited_once_with(HOTKEY_SCRIPT)

    @patch(
        "hauntedroom.flows.research.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.research.capture_page_grayscale",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.flows.research.find_template")
    async def test_research_flow_returns_to_available_after_active_is_gone(
        self,
        find_template,
        capture_page_grayscale,
        _load_template,
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        capture_page_grayscale.return_value = np.zeros((10, 10), dtype=np.uint8)
        find_template.side_effect = [
            (11, 22, 0.61),
            (33, 44, 0.62),
            (0, 0, 0.40),
            (55, 66, 0.63),
            (0, 0, 0.41),
            (0, 0, 0.42),
            (0, 0, 0.43),
            (0, 0, 0.44),
            (0, 0, 0.45),
            (0, 0, 0.46),
            (0, 0, 0.47),
            (0, 0, 0.48),
        ]

        completed = await run_research_flow(page)

        self.assertTrue(completed)
        self.assertEqual(find_template.call_count, 12)
        self.assertEqual(find_template.call_args_list[0].args[-1], "bottom_left")
        self.assertEqual(find_template.call_args_list[0].kwargs["scales"], (1.0,))
        self.assertEqual(len(find_template.call_args_list[1].args), 3)
        self.assertEqual(find_template.call_args_list[1].kwargs["scales"], (1.0,))
        self.assertEqual(find_template.call_args_list[8].args[-1], "bottom_left")
        self.assertEqual(
            page.mouse.click.await_args_list,
            [call(11, 22), call(33, 44), call(55, 66)],
        )

    @patch(
        "hauntedroom.flows.research.load_template",
        return_value=np.zeros((2, 2), dtype=np.uint8),
    )
    @patch(
        "hauntedroom.flows.research.capture_page_grayscale",
        new_callable=AsyncMock,
    )
    @patch("hauntedroom.flows.research.find_template")
    async def test_research_flow_checks_available_four_times_before_ending(
        self,
        find_template,
        capture_page_grayscale,
        _load_template,
    ):
        page = Mock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = Mock()
        page.mouse.click = AsyncMock()
        capture_page_grayscale.return_value = np.zeros((10, 10), dtype=np.uint8)
        find_template.side_effect = [
            (0, 0, score) for score in (0.40, 0.41, 0.42, 0.43)
        ]

        completed = await run_research_flow(page)

        self.assertTrue(completed)
        self.assertEqual(find_template.call_count, 4)
        self.assertEqual(page.wait_for_timeout.await_count, 3)
        page.mouse.click.assert_not_awaited()

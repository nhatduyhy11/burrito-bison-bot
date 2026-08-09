import asyncio
import importlib
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright

from hauntedroom.actions import loader as actions_loader
from hauntedroom.actions import runner as actions_runner
from hauntedroom.actions.loader import load_actions
from hauntedroom.actions.runner import run_actions
from hauntedroom.control_events import blockers as control_blockers
from hauntedroom.control_events import new_tab_blocker
from hauntedroom.control_events.new_tab_blocker import (
    install_game_core_frame_guard_after_delay,
    install_profile_popup_guard,
)
from hauntedroom.core import template, vision
from hauntedroom import settings
from hauntedroom.core.cli import prepare_runner
from hauntedroom.core.runtime import (
    ACTION_LOOP_COUNT,
    FlowControl,
    flow_checkpoint,
    save_live_screenshot,
    start_hotkey_listener,
    start_user_click_logger,
    wait_with_countdown,
    wait_for_ctrl_c,
)
from hauntedroom.flows import automap
from hauntedroom.flows import click_loop
from hauntedroom.flows import research
from hauntedroom.flows.automap_support import (
    boss_action,
    boss_detector,
    boss_flow,
    detectors,
    gear_action,
    hero_action,
    hero_levelup,
    map_completion,
    upgrade_action,
)
from hauntedroom.flows.click_loop import run_click_loop
from hauntedroom.flows.research import run_research_flow


START_BATTLE_TEMPLATE_NAME = "start_battle.png"
BETWEEN_MAPS_WAIT_MS = 2_000


def get_start_battle_actions(actions: list[dict]) -> list[dict]:
    """Return the shared start-room prefix, including the Start Battle click."""
    for index, action in enumerate(actions):
        template_path = action.get("_template_path")
        if (
            action.get("type") == "click_template"
            and isinstance(template_path, Path)
            and template_path.name == START_BATTLE_TEMPLATE_NAME
        ):
            return actions[: index + 1]

    raise ValueError(
        f"Actions do not contain a click_template for {START_BATTLE_TEMPLATE_NAME}."
    )


async def map_was_lost(page) -> bool:
    """Placeholder for the future map-loss detector."""
    return False


def reload_action_modules():
    """Reload modules used by JSON action flows and refresh imported callables."""
    global load_actions, run_actions

    importlib.invalidate_caches()
    importlib.reload(template)
    importlib.reload(vision)
    importlib.reload(new_tab_blocker)
    importlib.reload(control_blockers)
    reloaded_loader = importlib.reload(actions_loader)
    reloaded_runner = importlib.reload(actions_runner)
    load_actions = reloaded_loader.load_actions
    run_actions = reloaded_runner.run_actions
    print("Action support modules reloaded.", flush=True)
    return run_actions


def get_action_runner(dev_reload: bool = False):
    if not dev_reload:
        return run_actions
    return reload_action_modules()


def get_click_loop_flow(dev_reload: bool = False):
    global run_click_loop

    if not dev_reload:
        return run_click_loop

    importlib.invalidate_caches()
    reloaded_click_loop = importlib.reload(click_loop)
    run_click_loop = reloaded_click_loop.run_click_loop
    print("Click-loop module reloaded.", flush=True)
    return run_click_loop


def get_research_flow(dev_reload: bool = False):
    global run_research_flow

    if not dev_reload:
        return run_research_flow

    importlib.invalidate_caches()
    importlib.reload(template)
    importlib.reload(vision)
    reloaded_research = importlib.reload(research)
    run_research_flow = reloaded_research.run_research_flow
    print("Research modules reloaded.", flush=True)
    return run_research_flow


async def run_start_automap_loop(
    page,
    actions: list[dict],
    automap_flow,
    stop_event: asyncio.Event,
    debug: bool = False,
) -> bool:
    """Loop start-room -> auto-map -> loss check -> two-second cooldown."""
    start_actions = get_start_battle_actions(actions)
    loop_index = 0
    win_count = 0

    def record_win() -> int:
        nonlocal win_count
        win_count += 1
        return win_count

    while await flow_checkpoint(stop_event):
        loop_index += 1
        print("\n" + "=" * 60, flush=True)
        print(f"Start-auto loop {loop_index} start.", flush=True)

        started = await run_actions(
            page,
            start_actions,
            loop_count=2,
            stop_event=stop_event,
            stop_after_success=True,
        )
        if not started:
            return False

        print(
            f"Start-auto loop {loop_index}: entry actions finished; "
            "auto-map start.",
            flush=True,
        )
        map_completed = await automap_flow(
            page,
            stop_event,
            debug=debug,
            on_win=record_win,
        )
        if not map_completed:
            return False

        if await map_was_lost(page):
            print("Map loss detected; stopping start-auto loop.", flush=True)
            return True

        print("-" * 60, flush=True)
        waited = await wait_with_countdown(
            page,
            BETWEEN_MAPS_WAIT_MS,
            f"Start-auto loop {loop_index} cooldown",
            stop_event,
        )
        if not waited:
            return False

    return False


def get_automap_flow(dev_reload: bool = False):
    if not dev_reload:
        return automap.run_automap_flow

    reload_action_modules()
    importlib.reload(settings)
    importlib.reload(boss_detector)
    importlib.reload(detectors)
    importlib.reload(boss_action)
    importlib.reload(gear_action)
    importlib.reload(hero_levelup)
    importlib.reload(map_completion)
    importlib.reload(upgrade_action)
    importlib.reload(hero_action)
    importlib.reload(boss_flow)
    reloaded_automap = importlib.reload(automap)
    print("Auto-map support modules reloaded.", flush=True)
    return reloaded_automap.run_automap_flow


async def run_standby_controller(
    page,
    actions: list[dict],
    dev_reload: bool = False,
    debug: bool = False,
    actions_path: Optional[Path] = None,
) -> None:
    command_queue: asyncio.Queue[str] = asyncio.Queue()
    await start_hotkey_listener(page, command_queue)

    flow_task = None
    stop_event = None
    current_command = None
    command_names = {
        "1": "enter-exit room",
        "2": "auto-map battle",
        "3": "start-auto loop",
        "7": "fixed-position click loop",
        "9": "research",
    }
    print(
        "\n"
        "Haunted Room runner ready\n"
        "-------------------------\n"
        "  Shift+1    Enter / exit room\n"
        "  Shift+2    Auto-map battle\n"
        "  Shift+3    Start-auto loop / pause / resume\n"
        "  Shift+7    Click (440, 500) every 1s\n"
        "  Shift+8    Capture screenshot\n"
        "  Shift+9    Research\n"
        "  Shift+0    Stop current flow\n"
        "  Ctrl+C     Close runner\n"
        "-------------------------\n"
        "Runner idle.",
        flush=True,
    )

    command_task = asyncio.create_task(command_queue.get())
    try:
        while True:
            wait_for = {command_task}
            if flow_task is not None:
                wait_for.add(flow_task)

            done, _ = await asyncio.wait(wait_for, return_when=asyncio.FIRST_COMPLETED)

            if flow_task is not None and flow_task in done:
                try:
                    flow_task.result()
                except Exception as error:
                    print(f"Flow failed; runner is idle: {error}", flush=True)
                flow_task = None
                stop_event = None
                current_command = None
                print("Runner idle.", flush=True)

            if command_task not in done:
                continue

            command = command_task.result()
            command_task = asyncio.create_task(command_queue.get())
            if command == "0":
                if flow_task is None:
                    print("Runner is already idle.", flush=True)
                else:
                    print("Stopping current flow...", flush=True)
                    stop_event.set()
                continue

            if command == "8":
                await save_live_screenshot(page)
                if flow_task is None:
                    print("Runner idle.", flush=True)
                else:
                    print("Current flow continues.", flush=True)
                continue

            if command == "3" and current_command == "3" and flow_task is not None:
                if stop_event.is_paused:
                    stop_event.resume()
                    print("Start-auto loop resumed.", flush=True)
                else:
                    stop_event.pause()
                    print(
                        "Start-auto loop paused. Press Shift+3 to resume or "
                        "Shift+0 to stop.",
                        flush=True,
                    )
                continue

            if command not in command_names:
                print(f"Shift+{command}: no flow configured.", flush=True)
                continue

            if flow_task is not None:
                print(
                    f"Runner busy; press Shift+0 before starting Shift+{command}.",
                    flush=True,
                )
                continue

            action_runner = run_actions
            automap_flow = None
            click_loop_flow = run_click_loop
            research_flow = run_research_flow
            try:
                if command == "1":
                    action_runner = get_action_runner(dev_reload)
                elif command in {"2", "3"}:
                    automap_flow = get_automap_flow(dev_reload)
                elif command == "7":
                    click_loop_flow = get_click_loop_flow(dev_reload)
                elif command == "9":
                    research_flow = get_research_flow(dev_reload)

                if dev_reload and command in {"1", "3"} and actions_path is not None:
                    actions = load_actions(actions_path)
                    print(f"Actions reloaded from {actions_path}.", flush=True)
            except Exception as error:
                print(f"Dev reload failed; runner remains idle: {error}", flush=True)
                continue

            stop_event = FlowControl() if command == "3" else asyncio.Event()
            current_command = command
            print(f"Starting {command_names[command]} flow...", flush=True)
            if command == "1":
                flow_task = asyncio.create_task(
                    action_runner(
                        page,
                        actions,
                        loop_count=None,
                        stop_event=stop_event,
                    )
                )
            elif command == "2":
                flow_task = asyncio.create_task(
                    automap_flow(
                        page,
                        stop_event,
                        debug=debug,
                    )
                )
            elif command == "3":
                flow_task = asyncio.create_task(
                    run_start_automap_loop(
                        page,
                        actions,
                        automap_flow,
                        stop_event,
                        debug,
                    )
                )
            elif command == "7":
                flow_task = asyncio.create_task(click_loop_flow(page, stop_event))
            else:
                flow_task = asyncio.create_task(research_flow(page, stop_event))
    finally:
        command_task.cancel()
        await asyncio.gather(command_task, return_exceptions=True)
        if flow_task is not None:
            stop_event.set()
            await asyncio.gather(flow_task, return_exceptions=True)


async def main() -> None:
    args, actions, profile_dir = prepare_runner(load_actions)
    game_core_guard_task = None

    async with async_playwright() as playwright:
        launch_options = {
            "user_data_dir": str(profile_dir),
            "headless": args.headless,
            "viewport": {"width": args.width, "height": args.height},
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if args.browser != "chromium":
            launch_options["channel"] = args.browser

        context = await playwright.chromium.launch_persistent_context(**launch_options)

        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await install_profile_popup_guard(page)
            # The game can keep a parser-blocking resource pending long enough for
            # DOMContentLoaded to exceed Playwright's default 30-second timeout.
            # The automation uses visual polling, so it only needs the navigation
            # to be committed before its guards and controllers are started.
            await page.goto(args.url, wait_until="commit")
            game_core_guard_task = asyncio.create_task(
                install_game_core_frame_guard_after_delay(page)
            )
            await start_user_click_logger(page)

            if ACTION_LOOP_COUNT == 0:
                await run_standby_controller(
                    page,
                    actions,
                    args.dev_reload,
                    args.debug,
                    Path(args.actions),
                )
            else:
                await run_actions(page, actions)
                if args.keep_open:
                    await wait_for_ctrl_c(
                        page,
                        "Actions done. Press Ctrl+C to close this runner.",
                    )
        finally:
            if game_core_guard_task is not None:
                game_core_guard_task.cancel()
                await asyncio.gather(game_core_guard_task, return_exceptions=True)
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())

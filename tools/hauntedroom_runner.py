import asyncio
import importlib
from pathlib import Path

from playwright.async_api import async_playwright

from hauntedroom.actions.loader import load_actions
from hauntedroom.actions.runner import run_actions
from hauntedroom.control_events.new_tab_blocker import install_profile_popup_guard
from hauntedroom.core import vision
from hauntedroom.core.cli import prepare_runner
from hauntedroom.core.runtime import (
    ACTION_LOOP_COUNT,
    save_live_screenshot,
    start_hotkey_listener,
    start_user_click_logger,
    wait_with_countdown,
    wait_for_ctrl_c,
)
from hauntedroom.flows import automap
from hauntedroom.flows.automap_support import (
    boss_action,
    detectors as automap_detectors,
    hero_levelup,
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


async def run_start_automap_loop(
    page,
    actions: list[dict],
    automap_flow,
    stop_event: asyncio.Event,
) -> bool:
    """Loop start-room -> auto-map -> loss check -> two-second cooldown."""
    start_actions = get_start_battle_actions(actions)
    loop_index = 0
    win_count = 0

    def record_win() -> int:
        nonlocal win_count
        win_count += 1
        return win_count

    while not stop_event.is_set():
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
        pause_on_any_boss = loop_index >= 3 and win_count == 0
        if pause_on_any_boss:
            print(
                "No win recorded in the first two loops; the next boss "
                "will pause the game and stop the flow.",
                flush=True,
            )
        map_completed = await automap_flow(
            page,
            stop_event,
            pause_on_any_boss=pause_on_any_boss,
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

    importlib.invalidate_caches()
    importlib.reload(vision)
    importlib.reload(automap_detectors)
    importlib.reload(boss_action)
    importlib.reload(hero_levelup)
    reloaded_automap = importlib.reload(automap)
    print("Auto-map support modules reloaded.", flush=True)
    return reloaded_automap.run_automap_flow


async def run_standby_controller(
    page,
    actions: list[dict],
    dev_reload: bool = False,
) -> None:
    command_queue: asyncio.Queue[str] = asyncio.Queue()
    await start_hotkey_listener(page, command_queue)

    flow_task = None
    stop_event = None
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
        "  Shift+3    Start-auto loop\n"
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

            if command not in command_names:
                print(f"Shift+{command}: no flow configured.", flush=True)
                continue

            if flow_task is not None:
                print(
                    f"Runner busy; press Shift+0 before starting Shift+{command}.",
                    flush=True,
                )
                continue

            automap_flow = None
            if command in {"2", "3"}:
                try:
                    automap_flow = get_automap_flow(dev_reload)
                except Exception as error:
                    print(
                        f"Auto-map reload failed; runner remains idle: {error}",
                        flush=True,
                    )
                    continue

            stop_event = asyncio.Event()
            print(f"Starting {command_names[command]} flow...", flush=True)
            if command == "1":
                flow_task = asyncio.create_task(
                    run_actions(page, actions, loop_count=None, stop_event=stop_event)
                )
            elif command == "2":
                flow_task = asyncio.create_task(automap_flow(page, stop_event))
            elif command == "3":
                flow_task = asyncio.create_task(
                    run_start_automap_loop(
                        page,
                        actions,
                        automap_flow,
                        stop_event,
                    )
                )
            elif command == "7":
                flow_task = asyncio.create_task(run_click_loop(page, stop_event))
            else:
                flow_task = asyncio.create_task(run_research_flow(page, stop_event))
    finally:
        command_task.cancel()
        await asyncio.gather(command_task, return_exceptions=True)
        if flow_task is not None:
            stop_event.set()
            await asyncio.gather(flow_task, return_exceptions=True)


async def main() -> None:
    args, actions, profile_dir = prepare_runner(load_actions)

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
            await page.goto(args.url, wait_until="domcontentloaded")
            await start_user_click_logger(page)

            if ACTION_LOOP_COUNT == 0:
                await run_standby_controller(page, actions, args.dev_reload)
            else:
                await run_actions(page, actions)
                if args.keep_open:
                    await wait_for_ctrl_c(
                        page,
                        "Actions done. Press Ctrl+C to close this runner.",
                    )
        finally:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())

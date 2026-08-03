import asyncio
import importlib

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
        "7": "fixed-position click loop",
        "9": "research",
    }
    print(
        "Runner idle. Shift+1: enter-exit room; Shift+2: auto-map battle; "
        "Shift+7: click 440,500 every 1s; Shift+8: capture screenshot; "
        "Shift+9: research; "
        "Shift+0: stop current flow; Ctrl+C in terminal: close runner.",
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
            if command == "2":
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

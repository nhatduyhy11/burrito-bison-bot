import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from hauntedroom.control_events.new_tab_blocker import (
    install_game_core_frame_guard_after_delay,
    install_profile_popup_guard,
)
from hauntedroom.core.cli import prepare_runner
from hauntedroom.core.runtime import (
    start_user_click_logger,
)
from hauntedroom.runner.default_commands import FLOW_COMMANDS, SCREEN_FLOW_COMMANDS
from hauntedroom.runner.navigation import navigate_to_game
from hauntedroom.runner.standby import run_standby_controller


async def main() -> None:
    args, profile_dir = prepare_runner()
    game_core_guard_task = None

    async with async_playwright() as playwright:
        launch_options = {
            "user_data_dir": str(profile_dir),
            "headless": args.headless,
            "viewport": {"width": args.width, "height": args.height},
            "args": ["--disable-blink-features=AutomationControlled"],
            # The runner only needs cookies/local storage from this profile. A
            # stale game worker can otherwise interfere with a fresh navigation.
            "service_workers": "block",
        }
        if args.browser != "chromium":
            launch_options["channel"] = args.browser

        context = await playwright.chromium.launch_persistent_context(**launch_options)

        try:
            page = context.pages[0] if context.pages else await context.new_page()
            page = await navigate_to_game(
                context,
                page,
                args.url,
                prepare_page=install_profile_popup_guard,
            )
            game_core_guard_task = asyncio.create_task(
                install_game_core_frame_guard_after_delay(page)
            )
            await start_user_click_logger(page)

            await run_standby_controller(
                page,
                [],
                FLOW_COMMANDS,
                args.dev_reload,
                args.debug,
                Path(args.actions),
                SCREEN_FLOW_COMMANDS,
            )
        finally:
            if game_core_guard_task is not None:
                game_core_guard_task.cancel()
                await asyncio.gather(game_core_guard_task, return_exceptions=True)
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())

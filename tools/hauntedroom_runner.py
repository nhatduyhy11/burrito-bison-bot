import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from hauntedroom.actions.loader import load_actions
from hauntedroom.actions.runner import run_actions
from hauntedroom.control_events.new_tab_blocker import (
    install_game_core_frame_guard_after_delay,
    install_profile_popup_guard,
)
from hauntedroom.core.cli import prepare_runner
from hauntedroom.core.runtime import (
    ACTION_LOOP_COUNT,
    start_user_click_logger,
    wait_for_ctrl_c,
)
from hauntedroom.runner.default_commands import FLOW_COMMANDS
from hauntedroom.runner.standby import run_standby_controller


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
                    FLOW_COMMANDS,
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

import argparse
from pathlib import Path
from typing import Callable


GAME_URL = "https://hauntedroomvnh5.joynetgame.com/"
DEFAULT_VIEWPORT_WIDTH = 640
DEFAULT_VIEWPORT_HEIGHT = 720
DEFAULT_BROWSER = "chrome"
DEFAULT_PROFILE_DIR = Path(".tmp/hauntedroom-profile")


def prepare_runner(
    action_loader: Callable[[Path], list[dict]],
) -> tuple[argparse.Namespace, list[dict], Path]:
    parser = argparse.ArgumentParser(
        description=(
            "Run template/click/wait automation for Haunted Room in a "
            "persistent browser profile."
        )
    )
    parser.add_argument(
        "--actions",
        default="tools/hauntedroom_actions.sample.json",
        help="JSON file containing template, blocker, click, or wait actions.",
    )
    parser.add_argument(
        "--profile",
        default=str(DEFAULT_PROFILE_DIR),
        help=(
            "Persistent browser profile directory. "
            "Cookies and local storage are kept here."
        ),
    )
    parser.add_argument("--url", default=GAME_URL)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--browser",
        choices=("chrome", "msedge", "chromium"),
        default=DEFAULT_BROWSER,
        help=(
            "Browser channel to use. Chrome and Edge are discovered by Playwright "
            "on the current OS; chromium requires a Playwright-managed browser install."
        ),
    )
    parser.add_argument("--width", type=int, default=DEFAULT_VIEWPORT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_VIEWPORT_HEIGHT)
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep the browser open after actions finish.",
    )
    parser.add_argument(
        "--dev-reload",
        action="store_true",
        help=(
            "Reload auto-map and vision modules whenever Shift+2 or Shift+3 "
            "starts, while "
            "keeping the current browser session open."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug artifacts, including hero fallback screenshots.",
    )
    args = parser.parse_args()

    # Standby mode still needs the actions so a hotkey can start the flow later.
    actions = action_loader(Path(args.actions))
    profile_dir = Path(args.profile)
    profile_dir.mkdir(parents=True, exist_ok=True)
    return args, actions, profile_dir

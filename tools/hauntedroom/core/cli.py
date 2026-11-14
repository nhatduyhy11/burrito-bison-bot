import argparse
import os
from pathlib import Path
from urllib.parse import urlencode

CN_URL = "https://hauntheroesweb.acenetgame.com/"
VN_URL = "https://hauntedroomvnh5.joynetgame.com/"
YGKKSY_URL = "http://sy.betainc.store/ygkksy/index.php"
YGKKSY_QUERY_ENV = {
    "pass": "YGKKSY_PASS",
    "account": "YGKKSY_ACCOUNT",
    "token": "YGKKSY_TOKEN",
    "timestamp": "YGKKSY_TIMESTAMP",
}

DEFAULT_VIEWPORT_WIDTH = 640
DEFAULT_VIEWPORT_HEIGHT = 720
DEFAULT_BROWSER = "chrome"
DEFAULT_PROFILE_DIR = Path(".tmp/hauntedroom-profile")
YGKKSY_PROFILE_DIR = Path(".tmp/ygkksy-profile")


def prepare_runner() -> tuple[argparse.Namespace, Path]:
    parser = argparse.ArgumentParser(
        description=(
            "Run template/click/wait automation for Haunted Room in a "
            "persistent browser profile."
        )
    )
    parser.add_argument(
        "--actions",
        default="tools/json_macro/macro.env.json",
        help="JSON action file loaded lazily whenever Shift+5 starts.",
    )
    parser.add_argument(
        "--profile",
        help=(
            "Persistent browser profile directory. "
            "Cookies and local storage are kept here."
        ),
    )
    server = parser.add_mutually_exclusive_group()
    server.add_argument(
        "--cn",
        action="store_true",
        help="Use the CN server. The VN server is used by default.",
    )
    server.add_argument(
        "--ygkksy",
        action="store_true",
        help=f"Open YGKKSY from environment credentials ({YGKKSY_PROFILE_DIR}).",
    )
    parser.add_argument(
        "--url",
        help="Override the URL selected by --cn or --ygkksy.",
    )
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
        "--dev-reload",
        action="store_true",
        help=(
            "Reload flow, template, and vision modules whenever Shift+1 "
            "dispatches a flow, while keeping the current browser session open."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable flow debug mode for development.",
    )
    args = parser.parse_args()
    if args.url is None and args.ygkksy:
        missing = [name for name in YGKKSY_QUERY_ENV.values() if not os.getenv(name)]
        if missing:
            parser.error(f"--ygkksy requires environment variables: {', '.join(missing)}")
        query = urlencode({key: os.environ[name] for key, name in YGKKSY_QUERY_ENV.items()})
        args.url = f"{YGKKSY_URL}?{query}"
    elif args.url is None:
        args.url = CN_URL if args.cn else VN_URL

    if args.profile is None:
        args.profile = str(YGKKSY_PROFILE_DIR if args.ygkksy else DEFAULT_PROFILE_DIR)
    profile_dir = Path(args.profile)
    profile_dir.mkdir(parents=True, exist_ok=True)
    return args, profile_dir

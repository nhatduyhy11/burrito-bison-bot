"""Small, dependency-free helpers for readable terminal output."""

import os
import sys
from typing import Optional, TextIO


GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
ORANGE = "\033[38;5;208m"
BLUE = "\033[36m"
RESET = "\033[0m"


def colorize(text: str, color: str, *, stream: Optional[TextIO] = None) -> str:
    """Wrap text in ANSI color codes when writing to an interactive terminal."""
    output = sys.stdout if stream is None else stream
    if os.environ.get("NO_COLOR") is not None or not output.isatty():
        return text
    return f"{color}{text}{RESET}"

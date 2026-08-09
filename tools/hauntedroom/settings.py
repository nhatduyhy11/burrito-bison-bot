"""Top-level runtime switches for Haunted Room automation.

These are intentionally source-level settings instead of CLI arguments. In
dev-reload mode, auto-map reads this module again when a new Shift+2/Shift+3
flow starts. Page injection is startup-only because already injected scripts
cannot be replaced cleanly in the active document.
"""

# Capture diagnostic screenshots when hero selection falls back to a
# non-priority, non-purple three-card layout.
CAPTURE_HERO_FALLBACK_SCREENSHOTS = True

# Install JavaScript/CSS guards for profile popup blocking and the H5 SDK iframe.
# This is read at runner startup; changing it requires restarting the runner.
ENABLE_SCRIPT_INJECTION = True

# Click rooms/exit_click.png once when a boss HP bar enters the critical upper
# region. This pauses the game and stops auto-map without clicking exit_confirm.
CLICK_EXIT_ON_BOSS = False

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
ENABLE_SCRIPT_INJECTION = False

# Hotkeys intercepted while the Shift+3 start-auto flow is running. Keep the
# action names unchanged and edit only the digit strings to remap controls.
# Every action must use a distinct digit from "0" through "9".
START_AUTO_HOTKEYS = {
    "pause_resume": "1",
    "pause_at_boss": "2",
    "pause_at_final_boss": "3",
    "stop": "0",
    "screenshot": "8",
}

# Haunted Room Auto Handoff

## Current Status

The click/wait automation runner is implemented and documented in `docs/README.md`.

Current implementation files:

- `tools/hauntedroom_runner.py`
- `tools/hauntedroom/core/runtime.py`
- `tools/hauntedroom/core/vision.py`
- `tools/hauntedroom_actions.sample.json`

The runner uses Playwright browser channels rather than hardcoded executable paths. Installed Chrome is the default, and `channel="chrome"` was verified successfully on Windows with Chrome `150.0.7871.115`.

Per-loop start/finish logging is implemented and flushed immediately.

## Constraints

- Keep the automation limited to browser-context input.
- Do not add server request replay, memory patching, anti-cheat bypass, or game protocol manipulation.
- Template matching and image recognition are not implemented yet.

## Validation

- Python syntax checks pass.
- CLI help and browser-channel argument parsing pass.
- A Chrome-channel persistent context launch completed successfully.
- A non-keep-open run completed successfully with the sample actions.
- A keep-open run launched successfully and remained open until manually closed.

## Environment Note

Playwright-managed Chromium is not installed on the original Windows test machine. Its download previously failed because of a self-signed certificate chain error. Installed Chrome/Edge channels avoid that dependency.

## Next Steps

Adjust the sample action JSON as the game flow changes. Keep the configured viewport fixed while recording and replaying coordinates.

After the click/wait flow is stable, possible future additions are:

- A simple screenshot capture action for manual coordinate calibration.
- Multiple named action files for login, intro skip, and daily flow.
- Optional dry-run or verbose logging.
- Template matching only if fixed coordinates become too brittle.

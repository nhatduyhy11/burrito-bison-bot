# Burrito Bison Bot

> Archived computer-vision reference implementation. Run the commands in this
> document from the `ref_cv/` directory; the active Haunted Room project lives
> at the repository root.

This is an example showing how a basic Computer Vision technique of Template Matching can be used to automate gameplay.
Goal of this exercise is simply to explore how far one can get by using only template matching in OpenCV to automate primary tasks within the game.

This exercise is based on [Burrito Bison: Launcha Libre](http://www.kongregate.com/games/JuicyBeast/burrito-bison-launcha-libre) free online game, a goal of which is to throw the main character as far as possible, crush gummy bears to gain gold, use gold to buy upgrades, and use upgrades to throw yourself as far as possible.
If you've never seen the game before, here is [a human playing it](https://youtu.be/VQve8LoiFyQ).

Why this game? The main reason is a fairly easily automatable gameplay. Controls require the player only use the mouse.
There is also the grinding factor, requiring the player grind coins for upgrades to progress.

## Notes

What works:

- Launching the character;
- Skipping Pinata ads;
- Skipping mission screen;
- Restarting the round;
- Using the rocket;

What doesn't work or could be improved:

- Rocket is used whenever it fills up. It could be better timed for when there are targets below;
- Only a single blast of a rocket is used. At later game stages multiple available blasts could be used when necessary;
- Special capabilities gained from gummy bears aren't used (targeting with barrels, rockets, jumping jack);
- Player launch isn't timed or targeted. This may cause slower speeds at start, or completely miss the opponent;
- Some screens are not skipped, e.g. cards gained, unlocked items;
- Shopping for upgrades.

As it is right now, the bot can work semi-autonomously, requiring help to start the game, buy new upgrades and help it get past non-automated screens (such as new upgrade notices).

## Requirements

- Python 3.9+
- See [`pyproject.toml`](pyproject.toml) for the full list (OpenCV, NumPy, mss, Pillow, pynput).

## Installation

Dependencies are declared once in `pyproject.toml`; both tools below read them from there.

### Option A — `uv` (recommended)

[`uv`](https://docs.astral.sh/uv/) creates the virtual environment and installs the exact locked versions in seconds:

```bash
uv sync
```

You don't need to activate anything — run commands through `uv run`, which uses `.venv` automatically:

```bash
uv run main.py
```

### Option B — `pip` (fallback)

If you don't have `uv`, standard `pip` reads the same dependencies from `pyproject.toml`:

```bash
python -m venv venv
# Windows (PowerShell/cmd): venv\Scripts\activate
# macOS/Linux:              source venv/bin/activate
pip install .
```

Then run with:

```bash
python main.py
```

### Notes

- OpenCV comes from the [`opencv-python`](https://pypi.org/project/opencv-python/) wheel, which ships prebuilt binaries for Windows, macOS and Linux. No global install or source build is required.
- Earlier versions of this README installed OpenCV system-wide and used `virtualenv --system-site-packages`. That is no longer needed — all dependencies live inside the virtual environment.

## Running the bot

1) Run a resized version of Burrito Bison in your browser with `cd website && python -m http.server 8080`
2) Open up `http://localhost:8080` in your browser
3) Run the bot with `uv run main.py` (or `python main.py` if you used the pip flow)
4) Switch to the browser and ensure that the game screen is fully visible on your screen in the top left corner.
5) Go through the interfaces manually and put the game into a state where you would launch the bison from the Ring. The bot should pick it up and launch the hero from there.

Tips:

- This bot can no longer be run on Kongregate's website, you have to run a resized version of the game locally. This bot was tailored for Burrito Bison game to be run in 1173x660 px game screen, however Kongregate has since changed their design slightly, running the game in 1280x768 resolution, which throws off scaling in image templates.
- The bot is configured to work only with 1920x1080 screen resolution. If you have an HD (1366x768) or a 4K monitor, you may need to play around with game screen placement, or change observed area in `vision.py`

"""The profile setup page (web/setup.html) for `sandbox --setup`: its "Chơi" button picks the
captured battle, seed and profile of the next --play run."""

import asyncio
import json
import re

SETUP_PAGE = "/__sim/setup.html"
UUID_RE = re.compile(r"^[0-9a-f]{24}$")


class SetupPage:
    def __init__(self, page, origin, profiles_dir, root):
        self.page, self.origin, self.profiles_dir, self.root = page, origin, profiles_dir, root
        self._chosen = None  # future for the choose() call in progress

    @classmethod
    async def install(cls, page, origin, profiles_dir, root):
        """Expose window.simPlay({battle, seed, profile}) for the "Chơi" button (once per page: it
        stays across navigations, so the page can come back to setup)."""
        self = cls(page, origin, profiles_dir, root)
        await page.expose_function("simPlay", self._sim_play)
        return self

    async def _sim_play(self, choice):
        battle, seed, profile = choice.get("battle"), choice.get("seed") or None, choice.get("profile")
        if not isinstance(battle, str) or not UUID_RE.match(battle):
            raise ValueError(f"invalid battle uuid: {battle!r}")
        if seed is not None and seed != "random" and not UUID_RE.match(str(seed)):
            raise ValueError(f"invalid seed: {seed!r}")
        if not isinstance(profile, dict):
            raise ValueError("profile must be an object")
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        setup = {"battle": battle, "seed": seed, "profile": profile}
        for name, data in (("last.json", profile), ("last-setup.json", setup)):
            (self.profiles_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rel = (self.profiles_dir / "last.json").relative_to(self.root).as_posix()
        print(f"setup: battle {battle}, seed {seed or 'captured'}, profile saved to {rel}", flush=True)
        if self._chosen and not self._chosen.done():
            self._chosen.set_result(setup)
        return rel

    async def choose(self):
        """Show the setup page until its "Chơi" button is pressed. Returns that choice
        ({battle, seed, profile}, already saved under profiles_dir), or None if the window was closed first."""
        chosen = self._chosen = asyncio.get_running_loop().create_future()
        await self.page.goto(self.origin + SETUP_PAGE, wait_until="domcontentloaded")
        print(f"setup page open: {self.origin + SETUP_PAGE}", flush=True)
        while not chosen.done():
            if self.page.is_closed():
                return None
            await asyncio.sleep(0.3)
        return chosen.result()

from urllib.parse import urlsplit


PROFILE_POPUP_HOST = "cp.hhgame.vn"
PROFILE_POPUP_PATH_PREFIX = "/v2/user/profile/"
HIDE_GAME_CORE_FRAME_SCRIPT = """() => {
    const id = "haunted-room-hide-hwss-frame";
    if (document.getElementById(id)) return;
    document.head.appendChild(Object.assign(document.createElement("style"), {
        id,
        textContent: "#hwssH5GameCoreframe{visibility:hidden!important}",
    }));
}"""
PROFILE_POPUP_GUARD_SCRIPT = """(() => {
    if (window.__hauntedRoomProfilePopupGuard) return;
    window.__hauntedRoomProfilePopupGuard = true;

    const isProfileUrl = (value) => {
        try {
            const url = new URL(String(value), document.baseURI);
            return url.protocol === "https:" &&
                url.hostname === "cp.hhgame.vn" &&
                url.pathname.startsWith("/v2/user/profile/");
        } catch (_) {
            return false;
        }
    };
    const block = (url) => {
        return isProfileUrl(url);
    };

    const originalOpen = window.open;
    window.open = function(url, ...args) {
        if (block(url)) return null;
        return originalOpen.call(this, url, ...args);
    };
    document.addEventListener("click", (event) => {
        const anchor = event.target?.closest?.("a[href]");
        if (!anchor || !block(anchor.href)) return;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);
    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (!form || !block(form.action)) return;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);
})()"""


def is_profile_popup_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == PROFILE_POPUP_HOST
        and parsed.path.startswith(PROFILE_POPUP_PATH_PREFIX)
    )


async def install_profile_popup_guard(page) -> None:
    """Prevent known profile popups initiated by the game page."""
    await page.add_init_script(PROFILE_POPUP_GUARD_SCRIPT)
    for frame in page.frames:
        try:
            await frame.evaluate(PROFILE_POPUP_GUARD_SCRIPT)
        except Exception:
            # A frame can navigate or detach while the guard is being installed.
            continue


async def hide_game_core_frame(page) -> None:
    """Hide the game-core iframe overlay without adding duplicate styles."""
    await page.evaluate(HIDE_GAME_CORE_FRAME_SCRIPT)


async def close_profile_popup_tabs(page, label: str = "blocker") -> int:
    """Close profile tabs, restore the game tab, and hide their source overlay."""
    popup_pages = [
        candidate
        for candidate in list(page.context.pages)
        if candidate is not page and is_profile_popup_url(candidate.url)
    ]
    if not popup_pages:
        return 0

    for popup_page in popup_pages:
        try:
            await popup_page.close()
        except Exception:
            # The popup may already have been closed by the browser/user.
            pass

    await hide_game_core_frame(page)
    await page.bring_to_front()
    print(
        f"{label}: closed {len(popup_pages)} hhgame profile popup tab(s); "
        "hid #hwssH5GameCoreframe",
        flush=True,
    )
    return len(popup_pages)

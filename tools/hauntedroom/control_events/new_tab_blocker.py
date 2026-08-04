from urllib.parse import urlsplit


PROFILE_POPUP_HOST = "cp.hhgame.vn"
PROFILE_POPUP_PATH_PREFIX = "/v2/user/profile/"
GAME_CORE_FRAME_GUARD_SCRIPT = """(() => {
    if (window.__hauntedRoomGameCoreFrameGuard) return;

    const hideFrame = () => {
        const frame = document.getElementById("hwssH5GameCoreframe");
        if (!frame) return;

        if (
            frame.style.getPropertyValue("display") !== "none" ||
            frame.style.getPropertyPriority("display") !== "important"
        ) {
            frame.style.setProperty("display", "none", "important");
        }
        if (
            frame.style.getPropertyValue("pointer-events") !== "none" ||
            frame.style.getPropertyPriority("pointer-events") !== "important"
        ) {
            frame.style.setProperty("pointer-events", "none", "important");
        }
    };

    const install = () => {
        if (window.__hauntedRoomGameCoreFrameGuard) return;
        if (!document.documentElement) {
            queueMicrotask(install);
            return;
        }

        window.__hauntedRoomGameCoreFrameGuard = new MutationObserver(hideFrame);
        window.__hauntedRoomGameCoreFrameGuard.observe(document.documentElement, {
            subtree: true,
            childList: true,
            attributes: true,
            attributeFilter: ["id", "class", "style"],
        });
        hideFrame();
    };

    install();
})()"""
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


async def install_game_core_frame_guard(page) -> None:
    """Continuously hide the known non-game iframe in current and future pages."""
    await page.add_init_script(GAME_CORE_FRAME_GUARD_SCRIPT)
    for frame in page.frames:
        try:
            await frame.evaluate(GAME_CORE_FRAME_GUARD_SCRIPT)
        except Exception:
            # A frame can navigate or detach while the guard is being installed.
            continue


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

    await page.bring_to_front()
    print(
        f"{label}: closed {len(popup_pages)} hhgame profile popup tab(s); "
        "game-core iframe guard remains active",
        flush=True,
    )
    return len(popup_pages)

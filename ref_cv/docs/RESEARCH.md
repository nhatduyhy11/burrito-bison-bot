# Research: Headless Browser vs. Headful Background Mode

This document outlines the architectural and functional differences between running browser automation in **Headless Mode** versus **Headful Background Mode** (running a normal browser window in the background or minimized).

---

## 1. Executive Summary

| Feature / Metric | Headless Mode | Headful Background Mode |
| :--- | :--- | :--- |
| **GUI Window** | None (Fully in-memory offscreen rendering) | Yes (Normal browser window exists) |
| **Visible in Taskbar** | No | Yes |
| **Resource Usage** | Low (Low CPU, RAM, and GPU footprint) | High (Normal browser overhead) |
| **Anti-Bot Evasion** | Weak (Easily detected by Cloudflare/Akamai) | Strong (Behaves like a regular browser) |
| **Execution Speed** | Fast (No GUI rendering/compositing delay) | Standard |
| **Server/CI Support** | Excellent (Docker, headless Linux servers) | Poor (Requires virtual display servers like Xvfb) |
| **Canvas/JS Throttling** | None (Runs at full speed) | High (OS throttles inactive background tabs) |

---

## 2. Headless Mode (Fully Offscreen)

In **Headless Mode**, the browser runs without a graphical user interface. The HTML/CSS parsing, JavaScript execution, layout calculation, and canvas rendering happen entirely in memory.

### How it works under the hood
*   The page is drawn to a virtual off-screen buffer.
*   Frameworks like Playwright or Puppeteer take screenshots by extracting pixels directly from this off-screen buffer.
*   Synthetic events are dispatched directly to the layout engine (Blink/Webkit).

### Key Advantages
1.  **High Performance**: Skipping window compositing and rendering saves significant CPU/GPU resources, enabling you to run multiple instances concurrently.
2.  **Total Isolation**: Because there is no OS window, there is zero risk of it stealing focus or cluttering your taskbar.
3.  **Server compatibility**: Can run on headless Linux servers or inside lightweight Docker containers without needing graphics drivers.

### Drawbacks
*   **Easy to Detect**: Anti-bot protections (like Cloudflare, Akamai, or reCAPTCHA) look for headless signatures (e.g. `navigator.webdriver = true`, missing WebGL properties, specific screen dimensions).
*   **Rendering Differences**: Some Canvas or WebGL visual effects look different in headless Chrome due to the lack of hardware acceleration.

---

## 3. Headful Background Mode (Active Window, Lost Focus)

In **Headful Background Mode**, the automation tool launches a normal, visible browser window (like standard Google Chrome), but either starts it minimized, shifts focus to another app, or hides it behind other active windows.

### How it works under the hood
*   The browser operates as a standard desktop application.
*   The window is managed by the OS window manager (e.g., Windows Desktop Window Manager).
*   Even when covered by other windows, the browser receives synthetic click/input events via the Chrome DevTools Protocol (CDP).

### Key Advantages
1.  **Low Bot Detection**: Since it's a fully-featured browser window with standard headers, WebGL parameters, and system drivers, anti-bot scripts are much less likely to flag it.
2.  **Complete Web Standard Support**: Perfect rendering of Canvas, WebGL, audio/video codecs, and browser extensions.

### Drawbacks
1.  **Window Throttling (Critical for Game Bots)**: 
    To conserve system resources, Chromium-based browsers heavily throttle pages that are minimized or lack focus:
    *   `requestAnimationFrame` (commonly used for game loop ticks) is throttled from 60fps down to 1fps or paused entirely.
    *   `setTimeout` and `setInterval` timers are grouped and delayed.
2.  **Focus Conflicts**: Some web games stop execution or mute audio when the window loses focus (`document.hidden = true`).
3.  **Taskbar Presence**: The browser icon remains in your taskbar, which can be distracting.

---

## 4. Headless Mode Compatibility with Complex Games

There is a common misconception that complex interactive games cannot run in headless mode. 

### Can a complex game run in Headless Mode?
**Yes, it can.** 
Headless browsers (such as Headless Chromium used by Playwright) are not simple HTML parsers; they contain the exact same V8 JavaScript engine, DOM structure, CSS parser, and canvas drawing pipeline as standard browsers. 
*   **Canvas & WebGL**: Headless browsers support HTML5 2D canvas and 3D WebGL. They can render complex animations and physics engines.
*   **State & Networking**: WebSockets, Service Workers, LocalStorage, and IndexedDB work identically.
*   **Screenshots**: You can still capture full screenshots of the game board in memory to feed to template matching engines.

### Caveats for Headless Games
1.  **Software WebGL Rendering**: Since there is no physical monitor, the headless browser may fall back to software rendering (e.g. Google's SwiftShader) instead of utilizing your physical graphics card. For extremely GPU-heavy 3D games, this can cause frame drops and lag, which might affect time-sensitive bot actions.
2.  **Audio context constraints**: Some games require a user gesture (like a physical click) to start playing audio or rendering. Headless browsers can simulate these events, but you must ensure the script triggers the initial focus clicks correctly.

---

## 5. Background Windows, Partial Visibility, & TB (Testing Browser) Behavior

The user observed that if a browser window is in the background but **a small corner remains visible**, the game continues to run normally without freezing.

### The Science: Chromium's "Window Occlusion Tracker"
This behavior is due to a feature in Chromium (the codebase powering Chrome, Edge, and automated browsers) called **Window Occlusion Tracking**.
*   **Fully Covered / Minimized**: If Chromium detects that its window is 100% covered by other windows or minimized, it flags the window as `occluded`. To save CPU and power, it immediately throttles the tab (stopping canvas renders, throttling JS timers).
*   **Partially Visible (Even a Corner)**: If even a **single pixel** of the browser window is visible and not covered by another window, Chromium classifies it as `visible`. Therefore, **no background throttling is applied**, and the game loop runs at full speed.

### Does this apply to the TB (Testing Browser)?
**Yes, absolutely.**
The "Testing Browser" (TB) launched by Playwright, Puppeteer, or Selenium is not a simulated engine; it is a real, compiled Chromium/Firefox/WebKit binary running on your OS.
*   If you launch the TB in headful mode (`headless=False`) and cover it completely with another window, it will get throttled.
*   If you leave a small corner of the TB visible on your screen, it will run the game loop at normal speed.

```
┌────────────────────────┐
│   My Primary Window    │
│                        │     ┌──────────────┐
│                        │─────│ TB (Visible  │
│                        │     │  Corner)     │
└────────────────────────┘     │   [Running]  │
                               └──────────────┘
```

### The Professional Workaround (No Corner Needed)
Relying on keeping a corner of the window physically visible is fragile. Instead, you can instruct the Testing Browser (TB) to **disable occlusion tracking entirely** when launching it. This forces the browser to run at 100% speed even if it is completely hidden behind other windows:

```python
browser = playwright.chromium.launch(
    headless=False, # Running headful in background
    args=[
        # Disables Chromium's window occlusion tracking
        "--disable-backgrounding-occluded-windows",
        # Disables renderer process throttling
        "--disable-renderer-backgrounding",
        # Disables timer throttling for background tabs
        "--disable-background-timer-throttling"
    ]
)
```
Using these flags, the Testing Browser will run the game at full speed even when it is fully covered by your IDE, terminal, or other applications, eliminating the need to leave a visible corner.

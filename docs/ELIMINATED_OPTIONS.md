# Eliminated Automation Options & Suitability Critique

This document archives the technical architectures and options considered for the Burrito Bison Bot but ruled out due to incompatibilities with the project's core requirements.

---

## 1. Eliminated Option: OS-Level Window Messaging API (Win32 / OS Native)

This approach involves target-specific window handle (`HWND` on Windows) querying to post mouse event messages (`WM_LBUTTONDOWN`, `WM_MOUSEMOVE`, etc.) directly to the background browser window's queue, using Windows Graphics Capture (WGC) for background frame capture.

### Why it was Eliminated:

1.  **Violation of Cross-Platform Constraint (Critical)**:
    *   This architecture relies entirely on Windows OS-level APIs (e.g., `pywin32`, `ctypes` calling `user32.dll`, DXGI).
    *   It is completely unviable for running natively on macOS (which uses Quartz/Cocoa APIs) or Linux (which uses X11/Xtest or Wayland portals). To support all three platforms, we would have to write three entirely distinct, complex OS integration codebases.
2.  **Bypass of Game Engine Input**:
    *   Many modern browsers and hardware-accelerated canvas wrappers bypass standard OS message queues for input, querying raw/direct physical pointers. In these cases, OS-level window messages are ignored by the game engine.
3.  **Rendering Pause on Minimize**:
    *   Browsers pause rendering canvas frames when fully minimized to save system power. Therefore, background captures would freeze unless the window is kept open in the background (obscured but not minimized).

---

## 2. Eliminated Option: Network API Protocol Automation (Headless Client)

This approach involves sniffing WebSocket, HTTP, or TCP traffic during gameplay using network proxy tools and building a script to simulate game actions by sending direct raw packet messages or API calls to a backend server.

### Why it was Eliminated:

1.  **Pure Client-Side Canvas Architecture**:
    *   The game wrapper is a static HTML5 page embedding a local SWF/JS-compiled WebGL Canvas bundle.
    *   All calculations (gravity, speed, collision, coin counts, mission updates) happen entirely client-side inside the compiled canvas engine memory. 
    *   There is no backend server handling real-time gameplay ticks or character state.
2.  **No Network API Coverage**:
    *   Since there is no active gameplay API, there are no network packets to intercept, replay, or spoof. The bot has no choice but to interact visually and mechanically with the canvas representation of the game.

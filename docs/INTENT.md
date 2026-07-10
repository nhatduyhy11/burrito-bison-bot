# End-User Intent & Non-Technical Requirements: Burrito Bison Bot

This document outlines the desired behavior and goals of the Burrito Bison Bot from a non-technical end-user's perspective. It serves as the primary requirements document for the project.

---

## 1. Core Objective

The goal is to have a fully automated agent (a "bot") that plays the browser game **Burrito Bison: Launcha Libre** automatically, allowing the user to progress through the game, earn coins, and unlock upgrades without manual gameplay.

---

## 2. Primary Requirement: Non-Intrusive Background Execution

From the user's view, the absolute most important requirement is **multi-tasking capability**:

*   **No Mouse Hijacking**: The bot must **not** control, move, or click the user's actual physical mouse cursor. 
*   **Background Operation**: The game browser window must be able to run in the background (e.g., behind other active windows, on another virtual desktop, or minimized/headless).
*   **Freedom of Activity**: The user must be able to use their computer completely normally—typing, browsing, working, or playing other games—while the bot runs silently and independently in the background.

---

## 3. Gameplay Automation Requirements

The bot should replicate standard player behavior to loop rounds efficiently:

1.  **Launch Character**: 
    *   Pull back the launch slingshot at the start of a round and release it to launch the character into the arena.
    *   *Desirable*: Time the launch to get a "Perfect Launch" for maximum initial speed.
2.  **Use Rocket Boosters**: 
    *   Detect when the character's rocket booster meter is fully charged during a run.
    *   Trigger the booster immediately to keep the character in the air, smash more gummies, and sustain momentum.
3.  **Handle Pop-ups and Overlays (e.g., Pinatas)**: 
    *   Detect when random pop-ups occur (such as Pinata reward chests that require opening or canceling).
    *   Automatically dismiss these overlays to prevent the loop from getting stuck.
4.  **Manage Round Transition Loops**: 
    *   Detect when a round ends and the character stops moving.
    *   Click "Tap to Continue" on the mission/round summary screens.
    *   Click the "Next" button on the results screen to start a new round.
5.  **Adapt to Characters**:
    *   Support different launched heroes (e.g., Burrito Bison, Pineapple Spank, El Pollo) which may have different colors, UI meters, or positions.

---

## 4. User Experience (UX) Requirements

*   **Single-Step Start**: The user should be able to launch the bot using a single command (e.g., `python main.py`) without having to align windows, set screen scaling, or configure coordinates.
*   **Cross-Platform Compatibility**: The bot must run seamlessly on **Windows, macOS, and Linux**. The design and implementation cannot rely on operating-system-specific features (such as the Windows Win32 API) that restrict execution to a single platform.
*   **Resiliency**: The bot must recover if template matches are delayed, or if transient load times occur, without crashing or freezing.
*   **Low System Impact**: Running the background browser and bot logic should not lag or drag down the system performance of the user's active foreground tasks.

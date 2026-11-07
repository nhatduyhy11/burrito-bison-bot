"""Read manual reinjection requests from the focused CLI terminal."""

import os
import sys
import threading


REINJECT_COMMAND = "__reinject_hotkeys__"


class TerminalInput:
    def __init__(self, loop, command_queue):
        self.loop = loop
        self.command_queue = command_queue
        self._stop = threading.Event()
        self._thread = None
        self._fd = None
        self._terminal_state = None

    def start(self):
        if not sys.stdin.isatty():
            return
        try:
            if os.name != "nt":
                import termios
                import tty

                self._fd = sys.stdin.fileno()
                self._terminal_state = termios.tcgetattr(self._fd)
                tty.setcbreak(self._fd)
            self._thread = threading.Thread(target=self._read, daemon=True)
            self._thread.start()
        except (OSError, ValueError) as error:
            self.close()
            print(f"[reinject] Terminal input unavailable: {error}", flush=True)

    def _read(self):
        while not self._stop.is_set():
            if os.name == "nt":
                import msvcrt

                if not msvcrt.kbhit():
                    self._stop.wait(0.1)
                    continue
                char = msvcrt.getwch()
            else:
                import select

                ready, _, _ = select.select([self._fd], [], [], 0.1)
                if not ready:
                    continue
                char = os.read(self._fd, 1).decode(errors="ignore")
                if not char:
                    return
            if char == "|":
                self.loop.call_soon_threadsafe(
                    self.command_queue.put_nowait, REINJECT_COMMAND
                )

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.5)
        if self._terminal_state is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._terminal_state)
            self._terminal_state = None

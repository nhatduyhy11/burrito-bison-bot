"""Cross-platform process guards shared by the long-running browser tools.

Single-instance profile lock (refuse a second run on the same profile) and
signal-based stop handling. Deliberately free of anything socket- or
game-specific: just process/PID plumbing that behaves on both POSIX and
Windows.
"""

import asyncio
import os
import pathlib
import signal


def pid_alive(pid: int) -> bool:
    """Is a process with this PID running? Works on both POSIX and Windows.

    ``os.kill(pid, 0)`` is only a valid probe on POSIX: on Windows a dead PID
    raises a plain OSError (not ProcessLookupError) and a terminated process
    whose object still lingers silently succeeds, so ask the OS directly via
    OpenProcess + WaitForSingleObject instead.
    """
    if os.name == "nt":
        import ctypes

        SYNCHRONIZE, WAIT_TIMEOUT, ERROR_ACCESS_DENIED = 0x00100000, 0x0102, 5
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            # PID gone (invalid parameter) or not inspectable — mirror the
            # POSIX PermissionError convention and assume alive for the latter.
            return kernel32.GetLastError() == ERROR_ACCESS_DENIED
        try:
            return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass  # exists but not ours to signal — treat as alive
    return True


def acquire_profile_lock(
    profile_dir: pathlib.Path, lock_name: str = ".profile.lock"
) -> bool:
    """Refuse to start when another live process still holds the profile."""
    lock_path = profile_dir / lock_name
    profile_dir.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
        except ValueError:
            pid = None  # corrupt lock from a run that died without cleanup
        if pid is not None and pid_alive(pid):
            print(
                f"[guard] profile {profile_dir} is already held by PID {pid}; exiting.",
                flush=True,
            )
            return False
    lock_path.write_text(str(os.getpid()))
    return True


def release_profile_lock(
    profile_dir: pathlib.Path, lock_name: str = ".profile.lock"
) -> None:
    """Drop the lock file only if it still belongs to this process."""
    lock_path = profile_dir / lock_name
    try:
        if lock_path.read_text().strip() == str(os.getpid()):
            lock_path.unlink()
    except OSError:
        pass


def install_stop_signals(stop: asyncio.Event) -> None:
    """Make SIGTERM/SIGHUP (kill, terminal close) stop the process like Ctrl+C."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, getattr(signal, "SIGHUP", None)):
        if sig is None:
            continue  # Windows has no SIGHUP; Ctrl+C still stops the process
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass  # platform without add_signal_handler; Ctrl+C still stops the process

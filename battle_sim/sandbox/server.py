"""The offline mirror (battle_sim/serve.js) as a child process of the sandbox run."""

import asyncio
import os
import shutil
import subprocess
from contextlib import asynccontextmanager


def find_node() -> str:
    """node for serve.js: $BATTLE_SIM_NODE, else node on PATH."""
    node = os.environ.get("BATTLE_SIM_NODE") or shutil.which("node")
    if not node:
        raise SystemExit("node not found on PATH; set BATTLE_SIM_NODE to the full path of node(.exe)")
    return node


def start_server(root, port) -> subprocess.Popen:
    """Start serve.js and wait for its ready line (exits the run if it never comes)."""
    # A debug terminal (VS Code auto-attach, NODE_OPTIONS=--inspect) would attach to serve.js and
    # print "Debugger listening/attached" first; the server needs no debugger.
    env = {k: v for k, v in os.environ.items() if k not in ("NODE_OPTIONS", "VSCODE_INSPECTOR_OPTIONS")}
    proc = subprocess.Popen(
        [find_node(), str(root / "battle_sim" / "serve.js"), "--port", str(port)],
        cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
    )
    seen = []
    while len(seen) < 20:  # skip stray startup lines (debugger notices etc.) until the ready line
        line = proc.stdout.readline()
        if not line:
            break
        if "serving mirror" in line:
            print(line.strip(), flush=True)
            return proc
        seen.append(line.strip())
    proc.kill()
    raise SystemExit("serve.js did not start:\n  " + "\n  ".join(seen or ["(no output)"]))


@asynccontextmanager
async def mirror(root, port, emit):
    """Run serve.js for the duration of the block. Its output goes to `emit("server", line)`; the
    yielded list collects the paths it answered 404 (clear it between runs)."""
    proc = start_server(root, port)
    misses = []

    async def pump():
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, proc.stdout.readline)
            if not line:
                return
            line = line.rstrip()
            emit("server", line)
            if line.startswith("404 "):
                misses.append(line[4:])

    task = asyncio.create_task(pump())
    try:
        yield misses
    finally:
        proc.terminate()
        task.cancel()

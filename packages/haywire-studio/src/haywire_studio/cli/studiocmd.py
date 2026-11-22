"""``haywire studio`` — start, stop and check the studio of the current folder.

``start`` runs the studio in the background, in the current folder's Haywire
environment, waits until it answers, and prints its URL. Each folder keeps a
port of its own in ``.haywire/settings.json``: when another folder's studio
holds it, ``start`` takes the lowest free port from 8124 up and keeps that one.
``stop`` stops only a studio that ``start`` launched; a studio started by hand
(``uv run haywire``) is left alone unless ``--force``. ``status`` says what
holds the folder's port.

For an agent session the studio's tools then appear through the Farmhand
bridge (``haywire farmhand bridge``) with no reconnect.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

from haywire_studio.farmhand.bridge import find_project_root
from haywire_studio.farmhand.identity import identity_status, read_identity

DEFAULT_PORT = 8124
HOST = "127.0.0.1"
SETTINGS = Path(".haywire") / "settings.json"
_STARTED_PID = Path(".haywire") / "studio.pid"
LOG = Path(".haywire") / "studio.log"


@dataclass(frozen=True)
class PortState:
    """What holds a folder's port.

    ``holder`` is ``"free"``, ``"this folder"`` (this folder's live studio) or
    ``"other"`` (anything else); ``pid`` and ``folder`` name the other
    process when they can be found.
    """

    port: int
    holder: str
    pid: int | None = None
    folder: Path | None = None


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("studio", help="Start, stop or check the studio of the current folder")
    parser.add_argument(
        "--project",
        default=None,
        help="The project folder (default: the nearest folder above the current one that holds .haywire/).",
    )
    actions = parser.add_subparsers(dest="studio_command", required=True)

    start = actions.add_parser("start", help="Start the studio in the background and wait until it answers")
    start.add_argument(
        "--timeout", type=float, default=120.0, help="Seconds to wait (default: %(default)s)."
    )
    start.add_argument("--browser", action="store_true", help="Open the studio in a browser once it is up.")
    start.set_defaults(handler=_start)

    stop = actions.add_parser("stop", help="Stop the studio that 'haywire studio start' launched")
    stop.add_argument(
        "--force", action="store_true", help="Also stop a studio of this folder started by hand."
    )
    stop.set_defaults(handler=_stop)

    status = actions.add_parser("status", help="Show the folder's port and what holds it")
    status.set_defaults(handler=_status)


def _project(args: argparse.Namespace) -> Path:
    return Path(args.project).resolve() if args.project else find_project_root(Path.cwd())


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def folder_port(project: Path) -> tuple[int, str]:
    """Return the folder's studio port and where it comes from (its settings, or the default)."""
    port = _read_json(project / SETTINGS).get("network", {}).get("port", {}).get("value")
    if isinstance(port, int):
        return port, str(SETTINGS)
    return DEFAULT_PORT, "the default"


def save_port(project: Path, port: int) -> None:
    """Write ``port`` into the folder's ``.haywire/settings.json``, keeping every other setting."""
    path = project / SETTINGS
    settings = _read_json(path)
    settings.setdefault("network", {})["port"] = {"value": port}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def listening(port: int) -> bool:
    """Return whether anything accepts connections on ``port`` at 127.0.0.1."""
    with socket.socket() as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((HOST, port)) == 0


def own_studio(project: Path) -> dict | None:
    """Return this folder's live studio identity (its ``studio.json``), or ``None``."""
    ident = read_identity(project)
    if ident is None or identity_status(ident) != "alive":
        return None
    return ident


def port_state(project: Path, port: int) -> PortState:
    """Return what holds ``port``: nothing, this folder's studio, or something else."""
    ident = own_studio(project)
    if ident is not None and ident.get("port") == port and listening(port):
        return PortState(port, "this folder", pid=ident.get("pid"), folder=project)
    if not listening(port):
        return PortState(port, "free")
    pid = _listener_pid(port)
    folder = None
    if pid is not None:
        try:
            folder = Path(psutil.Process(pid).cwd())
        except psutil.Error:
            folder = None
    return PortState(port, "other", pid=pid, folder=folder)


def _listener_pid(port: int) -> int | None:
    """Return the pid listening on ``port``, best effort (``lsof`` may be missing)."""
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP@{HOST}:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    pids = [int(line) for line in out.split() if line.isdigit()]
    return pids[0] if pids else None


def free_port(start: int = DEFAULT_PORT) -> int:
    """Return the lowest port from ``start`` up that nothing listens on."""
    port = start
    while listening(port):
        port += 1
    return port


def studio_command(project: Path, *, browser: bool) -> list[str]:
    """Return the command that runs the studio of ``project`` in this environment."""
    command = [str(Path(sys.executable).with_name("haywire"))]
    return command if browser else [*command, "--no-browser"]


def _describe(state: PortState) -> str:
    if state.holder == "this folder":
        return f"this folder's studio (pid {state.pid})"
    if state.folder is not None:
        return f"the studio or process of {state.folder} (pid {state.pid})"
    return f"pid {state.pid}" if state.pid else "a process that cannot be identified"


def _start(args: argparse.Namespace) -> int:
    project = _project(args)
    port, source = folder_port(project)
    state = port_state(project, port)
    if state.holder == "this folder":
        print(f"The studio of {project} is already up: http://{HOST}:{port}")
        return 0
    if state.holder == "other":
        new = free_port(port + 1)
        save_port(project, new)
        print(f"Port {port} ({source}) is held by {_describe(state)}; this folder now uses {new}.")
        port = new

    log = project / LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    (project / ".haywire" / "studio.json").unlink(missing_ok=True)
    with log.open("w", encoding="utf-8") as out:
        process = subprocess.Popen(
            studio_command(project, browser=args.browser),
            cwd=project,
            stdout=out,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    (project / _STARTED_PID).write_text(str(process.pid), encoding="utf-8")

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            print(f"The studio exited during start (code {process.returncode}). Last lines of {log}:")
            _print_tail(log)
            (project / _STARTED_PID).unlink(missing_ok=True)
            return 1
        ident = own_studio(project)
        if ident is not None and listening(ident["port"]):
            print(f"The studio of {project} is up: http://{HOST}:{ident['port']} (log: {log})")
            return 0
        time.sleep(0.5)
    print(f"The studio did not answer within {args.timeout:.0f} s; it keeps starting. Log: {log}")
    return 1


def _stop(args: argparse.Namespace) -> int:
    project = _project(args)
    ident = own_studio(project)
    if ident is None:
        print(f"No studio of {project} is running.")
        (project / _STARTED_PID).unlink(missing_ok=True)
        return 0
    pid = ident["pid"]
    if not args.force and _started_pid(project) != pid:
        print(
            f"The studio of {project} (pid {pid}) was not started by 'haywire studio start': "
            "it is left running. Pass --force to stop it anyway."
        )
        return 1
    for sig, grace_s in ((signal.SIGINT, 15.0), (signal.SIGTERM, 8.0), (signal.SIGKILL, 2.0)):
        _signal(pid, sig)
        deadline = time.monotonic() + grace_s
        while time.monotonic() < deadline:
            if not _running(pid):
                (project / _STARTED_PID).unlink(missing_ok=True)
                print(f"The studio of {project} stopped.")
                return 0
            time.sleep(0.3)
    print(f"The studio of {project} (pid {pid}) did not stop.")
    return 1


def _running(pid: int) -> bool:
    """Return whether ``pid`` still runs; a process that exited but was not reaped yet does not."""
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def _started_pid(project: Path) -> int | None:
    try:
        return int((project / _STARTED_PID).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _signal(pid: int, sig: signal.Signals) -> None:
    """Signal the studio, and its children when it leads a process group of its own."""
    try:
        # Only a studio 'start' launched leads its group; a studio started by hand shares its
        # terminal's group, which must not get the signal too.
        if os.getpgid(pid) == pid:
            os.killpg(pid, sig)
        else:
            os.kill(pid, sig)
    except ProcessLookupError:
        return


def _status(args: argparse.Namespace) -> int:
    """Always exits 0 — reports rather than judges."""
    project = _project(args)
    port, source = folder_port(project)
    state = port_state(project, port)
    print(f"Folder: {project}")
    print(f"Port:   {port} ({source})")
    if state.holder == "free":
        print("Studio: not running")
    elif state.holder == "this folder":
        started = (
            "started by 'haywire studio start'" if _started_pid(project) == state.pid else "started by hand"
        )
        print(f"Studio: running, pid {state.pid}, {started}: http://{HOST}:{port}")
    else:
        print(f"Studio: the port is held by {_describe(state)}; 'haywire studio start' picks another one")
    return 0


def _print_tail(path: Path, lines: int = 20) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    for line in text[-lines:]:
        print(f"  | {line}")

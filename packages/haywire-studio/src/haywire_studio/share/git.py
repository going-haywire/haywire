"""Hardened ``git`` subprocess helpers for the share package.

Every git invocation ``share.py`` and the pipeline make goes through here. Two
rules the rest of the pipeline relies on:

1. **Nothing raises.** A missing binary, a non-zero exit, and a timeout all
   come back as a :class:`GitResult` so each step can decide what the failure
   means and raise its own domain exception.
2. **Remote calls cannot hang.** ``git_remote`` and ``git_remote_streaming``
   disable every credential-prompt path git has. Without this, a wizard run
   with no cached credential blocks forever on a prompt nobody can see: there
   is no TTY behind a NiceGUI event handler.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# GIT_CONFIG_NOSYSTEM keeps a system-wide credential helper from re-enabling a
# prompt we just disabled. The empty askpass values matter as much as the
# terminal-prompt flag: git falls back to GIT_ASKPASS/SSH_ASKPASS (and then to
# a GUI helper) when the terminal prompt is unavailable.
HARDENED_ENV: dict[str, str] = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "",
    "SSH_ASKPASS": "",
    "GIT_CONFIG_NOSYSTEM": "1",
}


@dataclass(frozen=True)
class GitResult:
    """Outcome of one git invocation. ``ok`` is True iff returncode == 0."""

    ok: bool
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False


def _hardened_env() -> dict[str, str]:
    """The parent environment with the prompt-disabling overlay applied.

    The parent env is preserved rather than replaced — dropping PATH would
    make git itself unfindable, and dropping HOME would lose the user's
    credential store, which is the thing we WANT git to consult.
    """
    env = dict(os.environ)
    env.update(HARDENED_ENV)
    return env


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: float,
    env: dict[str, str] | None,
) -> GitResult:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return GitResult(
            ok=False,
            stdout="",
            stderr=f"{' '.join(cmd)} timed out after {timeout:g}s",
            returncode=124,
            timed_out=True,
        )
    except OSError as exc:
        # Covers FileNotFoundError (binary missing) and its siblings, e.g.
        # PermissionError on a binary that exists but isn't executable. All of
        # these are "the process never started," so 127 — the shell's own
        # "command not found" convention — is the closest fit for either.
        return GitResult(ok=False, stdout="", stderr=f"{cmd[0]} not found: {exc}", returncode=127)
    return GitResult(
        ok=proc.returncode == 0,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        returncode=proc.returncode,
    )


def git(args: list[str], *, cwd: Path, timeout: float = 30.0) -> GitResult:
    """Run a purely local git command with the ambient environment."""
    return _run(["git", *args], cwd=cwd, timeout=timeout, env=None)


def git_remote(args: list[str], *, cwd: Path, timeout: float = 60.0) -> GitResult:
    """Run a git command that talks to a remote, with all prompts disabled."""
    return _run(["git", *args], cwd=cwd, timeout=timeout, env=_hardened_env())


def run(cmd: list[str], *, cwd: Path, timeout: float) -> GitResult:
    """Run an arbitrary non-git command synchronously, with the ambient environment.

    Same contract as :func:`git` (nothing raises, everything comes back as a
    :class:`GitResult`) for a non-git subprocess that doesn't need streaming —
    currently ``uv lock``. Like ``git``, this is a purely local call: no
    prompt-disabling env is applied.
    """
    return _run(cmd, cwd=cwd, timeout=timeout, env=None)


async def git_remote_streaming(
    args: list[str],
    *,
    cwd: Path,
    on_output: Callable[[str], None],
    timeout: float = 300.0,
) -> GitResult:
    """Run a remote git command, calling ``on_output`` per line as it arrives.

    stderr is merged into stdout: git writes transfer progress to stderr, so a
    caller wanting a single ordered log needs one stream.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=_hardened_env(),
        )
    except FileNotFoundError as exc:
        return GitResult(ok=False, stdout="", stderr=f"git not found: {exc}", returncode=127)

    lines: list[str] = []

    async def _drain() -> None:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            text = raw.decode(errors="replace").rstrip()
            on_output(text)
            lines.append(text)
        await proc.wait()

    try:
        await asyncio.wait_for(_drain(), timeout=timeout)
    except (TimeoutError, asyncio.TimeoutError):
        proc.kill()
        await proc.wait()
        return GitResult(
            ok=False,
            stdout="\n".join(lines),
            stderr=f"git {' '.join(args)} timed out after {timeout:g}s",
            returncode=124,
            timed_out=True,
        )

    output = "\n".join(lines)
    rc = proc.returncode if proc.returncode is not None else 1
    return GitResult(ok=rc == 0, stdout=output, stderr=output if rc != 0 else "", returncode=rc)


async def run_streaming(
    cmd: list[str],
    *,
    cwd: Path,
    on_output: Callable[[str], None],
    timeout: float = 900.0,
) -> GitResult:
    """Run an arbitrary command, streaming merged stdout/stderr per line.

    Same contract as :func:`git_remote_streaming` (nothing raises, everything
    comes back as a :class:`GitResult`) for non-git subprocesses — currently
    ``haywire docs``. The default timeout is generous: a full library-system
    boot plus per-node extraction is minutes, not seconds, on a large barn.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        return GitResult(ok=False, stdout="", stderr=f"{cmd[0]} not found: {exc}", returncode=127)

    lines: list[str] = []

    async def _drain() -> None:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            text = raw.decode(errors="replace").rstrip()
            on_output(text)
            lines.append(text)
        await proc.wait()

    try:
        await asyncio.wait_for(_drain(), timeout=timeout)
    except (TimeoutError, asyncio.TimeoutError):
        proc.kill()
        await proc.wait()
        output = "\n".join(lines)
        return GitResult(
            ok=False,
            stdout=output,
            stderr=f"{' '.join(cmd)} timed out after {timeout:g}s",
            returncode=124,
            timed_out=True,
        )

    output = "\n".join(lines)
    rc = proc.returncode if proc.returncode is not None else 1
    return GitResult(ok=rc == 0, stdout=output, stderr=output if rc != 0 else "", returncode=rc)

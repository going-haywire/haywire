"""Reading and writing the network settings behind the TLS and security commands.

**Reads resolve two tiers; writes target one.** The registry resolves
``local SET > workspace SET > global SET > default``, so a value in
``<workspace>/.haywire/settings.json`` beats the same value in
``~/.haywire/settings.json``. Reading only the global file makes these commands
report a configuration the studio will not actually run — the exact bug that
had ``security status`` printing "exposed" for a workspace that sets
``expose_to_network: false``. Writes still go to the global tier alone (D1):
TLS is a property of the machine, and a certificate path committed into a
project's workspace file would follow it onto machines where it does not exist.

**Why this is hand-rolled JSON rather than the settings API.** Constructing a
``SettingsRegistry()`` is not inert: it repoints ``FrameworkSettings._registry``
and drains the global pending-registration queue, so a throwaway registry built
inside a CLI silently steals framework-schema registration from the real one.
The file format is a stable, flat document, so reading it, merging two keys and
writing it back is both safer and simpler here.

**The stakes.** A real user's file already carries ``expose_to_network``,
``allowed_remote_ranges``, ``public_hostname`` and ``trusted_proxies``.
Clobbering those is the worst outcome this feature could produce, so every
write is read-modify-write, atomic, and refuses outright on a file it cannot
parse rather than replacing a hand-edited typo with a fresh document.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

NAMESPACE = "network"
CERTFILE_KEY = "ssl_certfile"
KEYFILE_KEY = "ssl_keyfile"


class SettingsWriteError(Exception):
    """The settings file could not be updated."""


def default_path() -> Path:
    """``~/.haywire/settings.json`` — the global tier (D1).

    Writes always land here. Reads do **not** stop here: see
    :func:`workspace_path` and :func:`read_network_setting`.
    """
    return Path.home() / ".haywire" / "settings.json"


def workspace_path() -> Path:
    """``<cwd>/.haywire/settings.json`` — the workspace tier.

    The studio takes its workspace root from ``os.getcwd()`` (see
    ``HaywireApp.__init__``), so a CLI run from the project directory resolves
    the same file the studio would.
    """
    return Path.cwd() / ".haywire" / "settings.json"


def workspace_overrides(*names: str) -> tuple[str, ...]:
    """Which of *names* the workspace tier sets, and therefore shadows.

    Writes go to the global tier, so a workspace file that sets the same key
    silently wins — ``ssl setup`` can report success while the studio keeps
    using a stale path and refuses to start. The commands that write are
    expected to call this and say so rather than let the user discover it at
    the next boot.
    """
    return tuple(name for name in names if _namespace_entry(workspace_path(), name) is not _UNSET)


def write_tls_paths(certfile: str, keyfile: str, *, path: Path | None = None) -> Path:
    """Merge the certificate and key paths into the settings file.

    Both are written together, always. Exactly one of the pair is the
    ``HALF_CONFIGURED`` state that hard-exits the studio at startup, and it is
    not a state this function is ever permitted to create.
    """
    target = path or default_path()
    data = _load_for_write(target)

    namespace = data.get(NAMESPACE)
    if not isinstance(namespace, dict):
        namespace = {}
        data[NAMESPACE] = namespace

    namespace[CERTFILE_KEY] = {"value": certfile}
    namespace[KEYFILE_KEY] = {"value": keyfile}

    _atomic_write_json(target, data)
    return target


def read_tls_paths(*, path: Path | None = None) -> tuple[str, str]:
    """The configured ``(certfile, keyfile)``, empty strings when unset.

    Tier-resolved (see :func:`read_network_setting`), so a workspace that sets
    its own certificate is reported as the studio would actually serve it.

    Never raises. ``status`` runs against whatever is on disk — including a
    broken file, which is precisely the situation the user needs reported.
    """
    certfile = read_network_setting(CERTFILE_KEY, path=path)
    keyfile = read_network_setting(KEYFILE_KEY, path=path)
    return (certfile if isinstance(certfile, str) else ""), (keyfile if isinstance(keyfile, str) else "")


def read_network_setting(name: str, *, path: Path | None = None) -> Any:
    """Read one value out of the ``network`` namespace, or ``None``.

    **Tier-resolved: workspace beats global.** The registry resolves
    ``local SET > workspace SET > global SET > default``
    (``haywire.core.settings.registry``), and reporting the global value alone
    is how this command came to print "exposed" for a studio whose workspace
    file turns exposure off. There is no local tier here — that one is per-node
    graph state, which network settings never have.

    Reads the files rather than the live registry because the CLI runs with the
    studio stopped, where no registry exists — and because constructing a
    throwaway ``SettingsRegistry()`` is not inert (see the module docstring).

    *path* overrides the **global** file only; the workspace tier still applies
    on top. Tests that need one file in play pass ``path`` and run in a
    workspace with no ``.haywire/settings.json``.
    """
    workspace = _namespace_entry(workspace_path(), name)
    if workspace is not _UNSET:
        return workspace
    global_value = _namespace_entry(path or default_path(), name)
    return None if global_value is _UNSET else global_value


class _Unset:
    """Distinguishes 'absent from this tier' from a legitimately stored ``None``."""


_UNSET = _Unset()


def _namespace_entry(target: Path, name: str) -> Any:
    """One setting from one file's ``network`` namespace, or ``_UNSET``."""
    data = _load_quietly(target)
    namespace = data.get(NAMESPACE)
    if not isinstance(namespace, dict) or name not in namespace:
        return _UNSET
    return _entry_value(namespace.get(name), None)


def _entry_value(entry: Any, fallback: Any) -> Any:
    """Unwrap ``{"value": x}``, tolerating a bare scalar.

    The store writes the table form but accepts scalars, and hand-edited files
    contain both.
    """
    if isinstance(entry, dict):
        return entry.get("value", fallback)
    return fallback if entry is None else entry


def _load_for_write(target: Path) -> dict[str, Any]:
    """Parse the file for a read-modify-write, refusing anything unparseable."""
    if not target.exists():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SettingsWriteError(
            f"{target} could not be parsed, so it was left untouched: {exc}\n"
            "Fix the file by hand (or move it aside) and run this again."
        ) from exc
    if not isinstance(raw, dict):
        raise SettingsWriteError(f"{target} does not contain a JSON object, so it was left untouched.")
    return raw


def _load_quietly(target: Path) -> dict[str, Any]:
    """Parse for reading; an unreadable file behaves as an empty one."""
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _atomic_write_json(target: Path, data: dict[str, Any]) -> None:
    """Write via temp + replace. A truncated settings.json is a studio that
    will not start, so a crash mid-write must leave the old file intact."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(target)
    except OSError as exc:
        raise SettingsWriteError(f"Could not write {target}: {exc}") from exc

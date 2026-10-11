"""Per-editor keymaps derived from the ``EditorCommand`` subscriptions of editor classes.

An editor class claims the ``default_keys`` of every ``EditorCommand`` it
subscribes to with ``@react_on`` / ``@redraw_on``. ``build_keymap`` resolves
those claims for one principal's access tier and records the problems that
keep a key from binding: clashes inside one editor, browser-reserved combos,
and a ``command_id`` declared by two classes. ``report_keymap_problems`` logs
those problems to the error ledger; ``report_new_keymap_problems`` logs only
the ones not yet logged in this process.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from haywire.core.access.tier import AccessTier
from haywire.core.errors.haywire_exception import ErrorSeverity, HaywireException
from haywire.core.session.handlers import discover_handlers
from haywire.core.signals import EditorCommand
from haywire.core.signals.keys import RESERVED_COMBOS

_CATEGORY = "Keyboard Shortcuts"

# Identity keys of the problems ``report_new_keymap_problems`` has logged in this process.
_reported_problems: set[tuple[Any, ...]] = set()


@dataclass(frozen=True)
class KeymapEntry:
    """One key combo bound to one command within an editor's keymap."""

    combo: str
    command: type[EditorCommand]


@dataclass(frozen=True)
class KeymapClash:
    """Two or more commands of one editor declaring the same combo.

    Attributes:
        editor_key: Registry key of the editor class.
        combo: The contested canonical combo.
        winner: The command the combo is bound to.
        losers: The other commands declaring the combo, in rank order.
    """

    editor_key: str
    combo: str
    winner: type[EditorCommand]
    losers: tuple[type[EditorCommand], ...]


@dataclass(frozen=True)
class Keymap:
    """The key bindings of every editor class, resolved for one access tier.

    Build one with ``build_keymap``.

    Attributes:
        editors: Editor key -> combo -> entry. Holds only editors that bind at
            least one combo.
        editor_labels: Editor key -> the editor's display label, for each key in
            ``editors``.
        commands: ``command_id`` -> command class, for every bindable command
            some editor subscribes to.
        clashes: Combos declared by more than one command of the same editor.
        reserved: ``(combo, command)`` pairs left unbound because the browser
            reserves the combo.
        duplicate_ids: ``(command_id, classes)`` for each id declared by more
            than one class; none of those classes appear in ``commands`` or
            ``editors``.
    """

    editors: Mapping[str, Mapping[str, KeymapEntry]]
    editor_labels: Mapping[str, str]
    commands: Mapping[str, type[EditorCommand]]
    clashes: tuple[KeymapClash, ...]
    reserved: tuple[tuple[str, type[EditorCommand]], ...]
    duplicate_ids: tuple[tuple[str, tuple[type[EditorCommand], ...]], ...]

    def to_client(self) -> dict[str, Any]:
        """Return the JSON-ready keymap for the browser key listener.

        Returns:
            ``{"editors": {editor_key: {combo: command_id}}, "native":
            {command_id: event_name}}``; ``native`` lists the commands whose data
            comes from a browser event (see ``EditorCommand.native_event``).
        """
        return {
            "editors": {
                editor_key: {combo: entry.command.command_id for combo, entry in entries.items()}
                for editor_key, entries in self.editors.items()
            },
            "native": {
                command_id: cmd.native_event
                for command_id, cmd in self.commands.items()
                if cmd.native_event is not None
            },
        }

    def editor_commands(self, editor_key: str) -> list[type[EditorCommand]]:
        """Return the commands bound in or shadowed within an editor, sorted by label.

        A command that loses every one of its combos to a clash is included;
        one whose only combos are browser-reserved is not. Returns an empty list
        for an editor key with no bindings.
        """
        found: set[type[EditorCommand]] = {e.command for e in self.editors.get(editor_key, {}).values()}
        for clash in self.clashes:
            if clash.editor_key == editor_key:
                found.update(clash.losers)
        return sorted(found, key=lambda cmd: (cmd.label, cmd.command_id))


def build_keymap(
    editor_classes: Mapping[str, type],
    can_access: Callable[[AccessTier], bool],
) -> Keymap:
    """Return the keymap of ``editor_classes`` for a principal allowed ``can_access``.

    Each editor binds the ``default_keys`` of the ``EditorCommand`` classes it
    subscribes to. A command whose ``access`` tier ``can_access`` rejects binds
    nothing, so its keys keep their browser behaviour. A browser-reserved combo
    is recorded in ``Keymap.reserved`` and left unbound. When several commands
    of one editor declare the same combo, the command from the editor class's
    own top-level package wins, then the lowest ``command_id``; the contest is
    recorded in ``Keymap.clashes``. A ``command_id`` declared by more than one
    class is recorded in ``Keymap.duplicate_ids`` and none of those classes bind.

    Args:
        editor_classes: Editor registry key -> editor class.
        can_access: Whether the principal holds the given tier.

    Example::

        keymap = build_keymap(
            {key: registry.get(key) for key in registry.list_names()},
            ctx.can_access,
        )
        report_keymap_problems(keymap)    # one ledger warning per problem
        payload = keymap.to_client()      # what the browser key listener reads
        keymap.editors[editor_key]["Mod+C"].command  # Copy, when that editor subscribes to it
    """
    subscriptions = {key: _subscribed_commands(cls) for key, cls in editor_classes.items()}

    declared: dict[str, list[type[EditorCommand]]] = {}
    for cmds in subscriptions.values():
        for cmd in cmds:
            classes = declared.setdefault(cmd.command_id, [])
            if cmd not in classes:
                classes.append(cmd)
    duplicate_ids = tuple(
        (command_id, tuple(sorted(classes, key=_qualified_name)))
        for command_id, classes in sorted(declared.items())
        if len(classes) > 1
    )
    duplicated = {command_id for command_id, _ in duplicate_ids}

    editors: dict[str, dict[str, KeymapEntry]] = {}
    editor_labels: dict[str, str] = {}
    commands: dict[str, type[EditorCommand]] = {}
    clashes: list[KeymapClash] = []
    reserved: set[tuple[str, type[EditorCommand]]] = set()

    for editor_key, cls in editor_classes.items():
        claims: dict[str, list[type[EditorCommand]]] = {}
        for cmd in subscriptions[editor_key]:
            if cmd.command_id in duplicated or not can_access(cmd.access):
                continue
            commands[cmd.command_id] = cmd
            for combo in cmd.default_keys:
                if combo in RESERVED_COMBOS:
                    reserved.add((combo, cmd))
                    continue
                claimants = claims.setdefault(combo, [])
                if cmd not in claimants:
                    claimants.append(cmd)
        if not claims:
            continue

        own_package = _top_package(cls)
        entries: dict[str, KeymapEntry] = {}
        for combo, claimants in sorted(claims.items()):
            ranked = sorted(claimants, key=lambda c: (_top_package(c) != own_package, c.command_id))
            entries[combo] = KeymapEntry(combo=combo, command=ranked[0])
            if len(ranked) > 1:
                clashes.append(
                    KeymapClash(
                        editor_key=editor_key, combo=combo, winner=ranked[0], losers=tuple(ranked[1:])
                    )
                )
        editors[editor_key] = entries
        identity = getattr(cls, "class_identity", None)
        editor_labels[editor_key] = getattr(identity, "label", None) or editor_key

    return Keymap(
        editors=editors,
        editor_labels=editor_labels,
        commands=commands,
        clashes=tuple(sorted(clashes, key=lambda c: (c.editor_key, c.combo))),
        reserved=tuple(sorted(reserved, key=lambda r: (r[0], r[1].command_id))),
        duplicate_ids=duplicate_ids,
    )


def report_keymap_problems(keymap: Keymap) -> None:
    """Log one warning to the error ledger per clash, reserved combo and duplicate id in ``keymap``."""
    for _key, message in _problems(keymap):
        _warn(message)


def report_new_keymap_problems(keymap: Keymap) -> None:
    """Log the problems in ``keymap`` that no earlier call in this process has logged.

    Works like ``report_keymap_problems``, but each problem is logged once per
    process however many keymaps contain it, so every session can report its
    own keymap without repeating the warnings of the others. A problem is
    identified by its kind, combo, editor key and command ids.
    ``reset_reported_keymap_problems`` forgets what has been logged.
    """
    for key, message in _problems(keymap):
        if key not in _reported_problems:
            _reported_problems.add(key)
            _warn(message)


def reset_reported_keymap_problems() -> None:
    """Forget which problems ``report_new_keymap_problems`` has logged, so each is logged again."""
    _reported_problems.clear()


def _problems(keymap: Keymap) -> list[tuple[tuple[Any, ...], str]]:
    """Return ``(identity key, warning message)`` for each problem in ``keymap``."""
    problems: list[tuple[tuple[Any, ...], str]] = []
    for clash in keymap.clashes:
        editor_label = keymap.editor_labels.get(clash.editor_key, clash.editor_key)
        losers = ", ".join(_describe(cmd) for cmd in clash.losers)
        key = (
            "clash",
            clash.editor_key,
            clash.combo,
            clash.winner.command_id,
            tuple(cmd.command_id for cmd in clash.losers),
        )
        problems.append(
            (
                key,
                f"Shortcut {clash.combo} in editor '{editor_label}' is bound to {_describe(clash.winner)}; "
                f"it shadows {losers}, which also declare it.",
            )
        )
    for combo, cmd in keymap.reserved:
        problems.append(
            (
                ("reserved", combo, cmd.command_id),
                f"Shortcut {combo} of {_describe(cmd)} is reserved by the browser and is not bound.",
            )
        )
    for command_id, classes in keymap.duplicate_ids:
        names = ", ".join(_qualified_name(cls) for cls in classes)
        problems.append(
            (
                ("duplicate", command_id),
                f"Command id '{command_id}' is declared by {names}; none of them get keyboard shortcuts.",
            )
        )
    return problems


def _subscribed_commands(cls: type) -> list[type[EditorCommand]]:
    """Return the ``EditorCommand`` classes with a ``command_id`` that ``cls`` subscribes to."""
    return [
        signal_type
        for signal_type in discover_handlers(cls)
        if issubclass(signal_type, EditorCommand) and getattr(signal_type, "command_id", None)
    ]


def _top_package(cls: type) -> str:
    return cls.__module__.split(".")[0]


def _qualified_name(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def _describe(cmd: type[EditorCommand]) -> str:
    return f"'{cmd.label}' ({cmd.command_id})"


def _warn(message: str) -> None:
    HaywireException.create(message, severity=ErrorSeverity.WARNING, category=_CATEGORY).log()

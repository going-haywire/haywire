"""The ``haywire-core`` requirement token — one parser, two producers.

A library's framework requirement lives in exactly one place: the
``haywire-core`` entry in its ``[project] dependencies``. The marketstall's
``require`` field is a *projection* of it, so the marketplace gate can answer
"will this install?" without cloning the repo.

Both producers of that projection — the share wizard and
``scripts/generate_marketstall.py`` — derive it through this module, so there
is one definition of what the token means rather than two that drift. (They
did drift: the two former implementations disagreed on the bare case below.)

The token carries the package name, not just the specifier, because a bare
specifier cannot distinguish two different states:

  * ``None``            — no ``haywire-core`` declaration at all
  * ``"haywire-core"``  — declared with NO floor, deliberately
  * ``"haywire-core>=0.0.38"`` — declared with a floor

The share wizard can produce the middle case (its "no-pin" option), so the
marketstall has to be able to say it. A bare-specifier field collapses the
first two into ``""`` and loses the author's intent.
"""

from __future__ import annotations

import re

CORE = "haywire-core"


def dependency_name(entry: str) -> str:
    """The bare distribution name from a PEP 508 dependency string.

    Strips extras, specifiers, environment markers, and direct references, so
    ``"visiongraph[onnx,openvino] >=0.5 ; sys_platform == 'darwin'"`` yields
    ``"visiongraph"``.
    """
    head = entry.split(";", 1)[0].split(" @ ", 1)[0]
    return re.split(r"[\[<>=!~ ]", head, maxsplit=1)[0].strip()


def haywire_core_requirement(dependencies: list[str]) -> str | None:
    """The ``haywire-core`` requirement token from a dependency list.

    Returns ``None`` when ``haywire-core`` is not declared, the bare name when
    it is declared without a specifier, and ``name + specifier`` otherwise.
    Those three are distinct states, not two — see the module docstring.

    Whitespace between name and specifier is dropped so the token is stable
    regardless of how the author spaced their pyproject entry.
    """
    for entry in dependencies:
        if dependency_name(entry).lower() != CORE:
            continue
        specifier = _specifier_of(entry)
        return f"{CORE}{specifier}" if specifier else CORE
    return None


def requirement_specifier(token: str) -> str:
    """The specifier portion of a requirement token, or "" when it has none.

    ``"haywire-core>=0.0.38"`` → ``">=0.0.38"``; ``"haywire-core"`` → ``""``.
    """
    return _specifier_of(token)


def _specifier_of(entry: str) -> str:
    """Everything after the distribution name, minus markers and extras."""
    head = entry.split(";", 1)[0].split(" @ ", 1)[0].strip()
    name = dependency_name(head)
    rest = head[len(name) :].strip()
    # Extras belong to the name, not the specifier: "foo[bar]>=1" → ">=1".
    if rest.startswith("["):
        _, _, rest = rest.partition("]")
        rest = rest.strip()
    # ">= 0.0.38" and ">=0.0.38" are the same requirement; normalizing here
    # keeps the emitted token stable no matter how the author spaced theirs.
    return re.sub(r"\s+", "", rest)

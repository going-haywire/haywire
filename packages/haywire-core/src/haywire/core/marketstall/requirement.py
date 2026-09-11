"""Read and write the ``haywire-core`` requirement token.

A library's framework requirement lives in the ``haywire-core`` entry of its
``[project] dependencies``; a marketstall's ``require`` field is a projection
of it, so the marketplace gate can answer "will this install?" without cloning
the repo.

The token carries the package name, not just the specifier, so that three
states stay distinct:

  * ``None``            — no ``haywire-core`` declaration at all
  * ``"haywire-core"``  — declared with no floor
  * ``"haywire-core>=0.0.38"`` — declared with a floor
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
    Whitespace between name and specifier is dropped, so the token does not
    depend on how the author spaced their pyproject entry.
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
    # ">= 0.0.38" and ">=0.0.38" are the same requirement, so strip the space.
    return re.sub(r"\s+", "", rest)

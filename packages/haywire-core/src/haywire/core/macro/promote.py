"""Turning a Group into a macro: plan first, then one write.

A stepper may only be built over an operation that can stop between reading and
writing, so promotion is two calls: :func:`plan_promotion` answers what would
be written and why it might be refused, and :func:`write_macro_file` performs
the single mutating step. See ``.insights/project_stepper_flows.md``.

Swapping the Group's card for a placement is the caller's to do, as one
undoable action group; this module owns the file.
"""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class PromotableSubgraph(Protocol):
    """What :func:`plan_promotion` reads off a Group's Subgraph.

    A Protocol rather than ``SubgraphDefinition`` itself: planning needs a
    label and a serialized document and nothing else, so the UI's tests can
    drive the flow without building a graph and a library system.
    """

    @property
    def label(self) -> str: ...

    def to_dict(self) -> dict: ...


#: A macro's filestem becomes its registry key and its menu entry.
_NAME_RULE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")

#: Suffix of a macro document.
MACRO_SUFFIX = ".hwm"

_FALLBACK_NAME = "Macro"


def name_refusal(name: str) -> str | None:
    """Why ``name`` cannot be a macro's filename, or ``None`` if it can.

    Returns:
        The reason, phrased for a dialog, or ``None`` when the name is usable.
    """
    if not name:
        return "Enter a name for the macro."
    if not _NAME_RULE.fullmatch(name):
        return "A macro name must start with a letter and hold only letters, digits, '_' or '-'."
    return None


def suggest_name(label: str) -> str:
    """Turn a Group's label into a name that passes :func:`name_refusal`.

    Accents are folded, runs of unusable characters become single underscores,
    and a label that survives none of that falls back to a generic name — a
    dialog must always open with something valid in the field.
    """
    folded = unicodedata.normalize("NFKD", label)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_only).strip("_")
    cleaned = re.sub(r"_{2,}", "_", cleaned)

    # The rule requires a leading letter, so drop anything before the first one.
    match = re.search(r"[A-Za-z]", cleaned)
    candidate = cleaned[match.start() :] if match else ""

    if name_refusal(candidate) is not None:
        return _FALLBACK_NAME
    return candidate[0].upper() + candidate[1:]


@dataclass
class PromotionPlan:
    """What promoting one Group would write, and why it might be refused.

    Read-only: holding a plan changes nothing on disk. ``refusal`` being set
    means :func:`write_macro_file` will raise rather than write.
    """

    path: Path
    registry_key_stem: str
    document: dict[str, Any] = field(default_factory=dict)
    refusal: str | None = None


def plan_promotion(
    definition: PromotableSubgraph,
    name: str,
    macros_folder: Path,
) -> PromotionPlan:
    """Describe the macro file ``definition`` would become.

    Checks the name rule, that nothing already occupies the path, and that the
    Subgraph holds the boundary pair a macro needs — the same containment the
    registry applies on load, checked here so the dialog can say so first.

    Args:
        definition: The Group's Subgraph, whose contents become the document.
        name: The macro's filestem, as typed by the user.
        macros_folder: The target library's ``macros/`` folder. It need not
            exist yet.

    Returns:
        The plan. Inspect ``refusal`` before writing.
    """
    path = macros_folder / f"{name}{MACRO_SUFFIX}"

    refusal = name_refusal(name)
    if refusal is not None:
        return PromotionPlan(path=path, registry_key_stem=name, refusal=refusal)

    if path.exists():
        return PromotionPlan(
            path=path,
            registry_key_stem=name,
            refusal=f"A macro named '{name}' already exists in this library.",
        )

    document = definition.to_dict()
    document.pop("key", None)

    containment = _containment_refusal(document)
    if containment is not None:
        return PromotionPlan(path=path, registry_key_stem=name, document=document, refusal=containment)

    return PromotionPlan(path=path, registry_key_stem=name, document=document)


def write_macro_file(plan: PromotionPlan) -> Path:
    """Write the planned macro document. The only step that touches disk.

    Creates the ``macros/`` folder when a library predates it.

    Raises:
        ValueError: The plan carries a refusal.

    Returns:
        The path written.
    """
    if plan.refusal is not None:
        raise ValueError(f"This Group cannot be promoted: {plan.refusal}")

    plan.path.parent.mkdir(parents=True, exist_ok=True)
    plan.path.write_text(json.dumps(plan.document, indent=2), encoding="utf-8")
    return plan.path


def _containment_refusal(document: dict[str, Any]) -> str | None:
    """Why this document would be refused as a macro, or ``None``.

    The same check the registry runs on load, so a promotion is refused in the
    dialog rather than written and then rejected on the next scan.
    """
    from haywire.core.macro.registry import validate_containment

    ok, reason = validate_containment(document)
    return None if ok else reason

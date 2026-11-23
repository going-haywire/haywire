"""The markdown files outside ``docs/`` that agents and people start from link to files that exist.

``mkdocs build --strict`` guards links inside ``docs/``; these files sit outside it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POINTERS = ["CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md", "README.md", "dev/README.md", "scripts/README.md"]
LINK = re.compile(r"\]\(([^)\s]+)\)")


def _local_targets(text: str) -> list[str]:
    targets = []
    for target in LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        targets.append(target.split("#", 1)[0])
    return [t for t in targets if t]


@pytest.mark.parametrize("pointer", POINTERS)
def test_every_local_link_resolves(pointer):
    path = ROOT / pointer
    missing = [t for t in _local_targets(path.read_text(encoding="utf-8")) if not (path.parent / t).exists()]
    assert not missing, f"{pointer} links to missing files: {missing}"

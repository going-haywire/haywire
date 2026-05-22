"""Sanity-check that the haybale-gen-docs skill's contract is documented."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_skill_md_documents_readme_generation() -> None:
    """SKILL.md must include a section about README.md generation."""
    skill_md = Path(__file__).parent.parent / ".claude" / "skills" / "haybale-gen-docs" / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    assert "README.md" in content
    # The marker-pair contract MUST be documented (spec §6.6).
    assert "marketstall:share-url:start" in content
    assert "marketstall:share-url:end" in content


@pytest.mark.unit
def test_format_spec_md_includes_readme() -> None:
    """format-spec.md must include a README.md canonical format section."""
    format_spec = Path(__file__).parent.parent / ".claude" / "skills" / "haybale-gen-docs" / "format-spec.md"
    content = format_spec.read_text(encoding="utf-8")
    assert "## README.md" in content

"""Comment-preserving TOML editing.

The property under test is the one `toml` cannot provide: a user's comments,
key order and layout survive a round trip that changes one value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from haywire.core.tomlio import edit_toml, read_toml, write_toml

pytestmark = pytest.mark.unit

_SAMPLE = """[project]
name = "demo"
# Pinned deliberately — see the release notes before bumping.
dependencies = [
    "alpha~=1.0",
    "beta",
]

[tool.uv.sources]
# alpha is vendored from git until upstream cuts a release.
alpha = { git = "https://example.com/alpha.git" }
"""


def _write(tmp_path: Path) -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(_SAMPLE)
    return path


def test_edit_preserves_comments(tmp_path: Path) -> None:
    path = _write(tmp_path)

    with edit_toml(path) as doc:
        doc["project"]["dependencies"].append("gamma~=2.0")

    body = path.read_text()
    assert "# Pinned deliberately — see the release notes before bumping." in body
    assert "# alpha is vendored from git until upstream cuts a release." in body
    assert "gamma~=2.0" in body


def test_edit_preserves_unrelated_sections(tmp_path: Path) -> None:
    path = _write(tmp_path)

    with edit_toml(path) as doc:
        doc["project"]["name"] = "renamed"

    body = path.read_text()
    assert "[tool.uv.sources]" in body
    assert 'alpha = { git = "https://example.com/alpha.git" }' in body


def test_removal_keeps_surrounding_comments(tmp_path: Path) -> None:
    """The uninstall shape: drop one dependency, keep everything else."""
    path = _write(tmp_path)

    with edit_toml(path) as doc:
        deps = doc["project"]["dependencies"]
        doc["project"]["dependencies"] = [d for d in deps if not str(d).startswith("alpha")]

    body = path.read_text()
    assert "alpha~=1.0" not in body
    assert "beta" in body
    assert "# Pinned deliberately" in body


def test_exception_inside_block_leaves_file_untouched(tmp_path: Path) -> None:
    """A partial edit must not be persisted — these run in best-effort paths."""
    path = _write(tmp_path)
    before = path.read_text()

    def _edit_then_fail() -> None:
        with edit_toml(path) as doc:
            doc["project"]["name"] = "half-applied"
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        _edit_then_fail()

    assert path.read_text() == before


def test_read_then_write_is_byte_identical(tmp_path: Path) -> None:
    """A no-op round trip must not reformat anything."""
    path = _write(tmp_path)

    write_toml(path, read_toml(path))

    assert path.read_text() == _SAMPLE


def test_values_read_back_as_expected(tmp_path: Path) -> None:
    path = _write(tmp_path)

    doc = read_toml(path)

    assert doc["project"]["name"] == "demo"
    assert list(doc["project"]["dependencies"]) == ["alpha~=1.0", "beta"]


def test_malformed_file_raises_toml_decode_error(tmp_path: Path) -> None:
    """The parser changed underneath callers; the exception type must not.

    dep_detect and the share pipeline both catch toml.TomlDecodeError to turn
    a malformed pyproject into a user-facing message. tomlkit raises its own
    ParseError, so read_toml translates.
    """
    import toml

    path = tmp_path / "broken.toml"
    path.write_text("[[[broken")

    with pytest.raises(toml.TomlDecodeError):
        read_toml(path)


def test_malformed_file_raises_before_any_write(tmp_path: Path) -> None:
    """edit_toml must fail on entry, never leaving a truncated file."""
    import toml

    path = tmp_path / "broken.toml"
    path.write_text("this is not = valid = toml")
    before = path.read_text()

    def _attempt() -> None:
        with edit_toml(path) as doc:
            doc["x"] = 1

    with pytest.raises(toml.TomlDecodeError):
        _attempt()

    assert path.read_text() == before

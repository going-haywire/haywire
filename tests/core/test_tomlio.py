"""Comment-preserving TOML editing.

The property under test is the one `toml` cannot provide: a user's comments,
key order and layout survive a round trip that changes one value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from haywire.core.tomlio import edit_toml, plain, read_toml, write_toml

pytestmark = pytest.mark.unit


def read_toml_string(body: str):
    """Parse *body* the way read_toml() does, without a file."""
    import tomlkit

    return tomlkit.parse(body)


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


# ─────────────────────────────────────────────────────────────────────────────
# plain(): the price of comment-preserving parsing.
#
# tomlkit's types subclass the builtins, so they satisfy isinstance, compare
# equal, and repr identically — and then misbehave in two places that look
# unrelated: toml.dumps writes a string out as its characters, and a tomlkit
# Array compares unequal to a plain list. Both were found and patched
# separately before this was one function.
# ─────────────────────────────────────────────────────────────────────────────


def test_tomlkit_values_are_builtin_subclasses() -> None:
    """The premise. If this ever stops holding, plain() is dead weight."""
    doc = read_toml_string('version = "0.0.36"\n')
    assert isinstance(doc["version"], str)
    assert doc["version"] == "0.0.36"
    assert type(doc["version"]) is not str


def test_plain_returns_exact_builtins() -> None:
    doc = read_toml_string(
        'version = "0.0.36"\ntags = ["a", "b"]\ncount = 2\nflag = true\nratio = 1.5\n\n[table]\nkey = "v"\n'
    )
    out = plain(doc)

    assert type(out["version"]) is str
    assert type(out["tags"]) is list
    assert all(type(v) is str for v in out["tags"])
    assert type(out["count"]) is int
    assert type(out["flag"]) is bool  # bool before int — it subclasses int
    assert type(out["ratio"]) is float
    assert type(out["table"]) is dict
    assert type(out["table"]["key"]) is str


def test_plain_output_serializes_as_scalars_not_character_sequences(tmp_path: Path) -> None:
    """The defect this exists to prevent, end to end.

    Without plain(), toml.dumps writes `version = ["0", ".", "0", ...]` — valid
    TOML, so nothing upstream complains, and the consumer rejects the file.
    """
    import toml

    doc = read_toml_string('version = "0.0.36"\ntags = ["a", "b"]\n')

    corrupt = toml.dumps(dict(doc))
    assert '"0", "."' in corrupt, "premise changed: toml.dumps no longer splits tomlkit strings"

    clean = toml.dumps(plain(doc))
    assert clean.strip() == 'version = "0.0.36"\ntags = [ "a", "b",]'
    assert toml.loads(clean)["version"] == "0.0.36"


def test_plain_preserves_equality() -> None:
    """Normalising must not change what a value means, only its type.

    Older tomlkit compared containers unequal to plain ones, which is why
    `publishing.generate` normalises both sides of its drift comparison. On
    0.15.1 they already compare equal — so what this pins is the safety
    property that still matters: plain() is not allowed to alter a value.
    """
    doc = read_toml_string('tags = ["a", "b"]\n\n[project]\nname = "demo"\n')
    assert plain(doc["tags"]) == doc["tags"] == ["a", "b"]
    assert plain(doc["project"]) == {"name": "demo"}


def test_plain_passes_through_what_it_does_not_know(tmp_path: Path) -> None:
    """Dates serialize and compare correctly already; do not stringify them."""
    doc = read_toml_string("when = 1979-05-27T07:32:00Z\n")
    assert plain(doc)["when"] == doc["when"]

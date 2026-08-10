"""The haybale.toml reader: the splat contract, every raise, both derivations."""

from pathlib import Path

import pytest

from haywire.core.library.haybale_toml import (
    HAYBALE_TOML,
    HaybaleTomlError,
    module_of,
    read_haybale_toml,
    read_haybale_toml_lenient,
    tag_for,
)

_FULL = """\
id = "core"
version = "0.0.40"
label = "Core"
on_reload = "restart"
linked_libraries = ["haybale_studio", "haybale_graph_editor"]
"""


def _write(tmp_path: Path, body: str) -> Path:
    (tmp_path / HAYBALE_TOML).write_text(body)
    return tmp_path


# ── the splat contract ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_reads_every_identity_field(tmp_path: Path) -> None:
    fields = read_haybale_toml(_write(tmp_path, _FULL))
    assert fields == {
        "id": "core",
        "version": "0.0.40",
        "label": "Core",
        "on_reload": "restart",
        "linked_libraries": ["haybale_studio", "haybale_graph_editor"],
    }


@pytest.mark.unit
def test_absent_keys_are_omitted_not_emptied(tmp_path: Path) -> None:
    """The splat contract: a caller updates defaults, so an absent key must not
    arrive as "" and clobber one."""
    fields = read_haybale_toml(_write(tmp_path, 'id = "core"\nversion = "0.0.40"\n'))
    assert fields == {"id": "core", "version": "0.0.40"}
    assert "label" not in fields
    assert "linked_libraries" not in fields


@pytest.mark.unit
def test_unknown_keys_are_ignored(tmp_path: Path) -> None:
    """`name` and the publishing coordinates are the marketstall row's
    business — they don't reach the identity, even though they live in the
    same file."""
    fields = read_haybale_toml(
        _write(
            tmp_path,
            'id = "core"\nversion = "0.0.40"\nname = "haybale-core"\n'
            'examples_path = "examples/"\nnotes = "NOTES.md"\n',
        )
    )
    assert fields == {"id": "core", "version": "0.0.40"}


@pytest.mark.unit
def test_homepage_and_first_author_project_onto_the_identity(tmp_path: Path) -> None:
    """The file is shaped for the marketstall row — repeatable [[authors]], and
    urls split by role. The identity carries one of each, so the reader projects
    the homepage and the first author onto it."""
    fields = read_haybale_toml(
        _write(
            tmp_path,
            'id = "core"\nversion = "0.0.40"\nhomepage_url = "https://example.com"\n'
            '\n[[authors]]\nname = "Alice"\nurl = "https://alice.example"\n'
            '\n[[authors]]\nname = "Bob"\n',
        )
    )
    assert fields["url"] == "https://example.com"
    assert fields["author"] == "Alice"
    assert fields["author_url"] == "https://alice.example"


@pytest.mark.unit
def test_author_without_a_url_is_fine(tmp_path: Path) -> None:
    fields = read_haybale_toml(
        _write(tmp_path, 'id = "core"\nversion = "0.0.40"\n\n[[authors]]\nname = "Alice"\n')
    )
    assert fields["author"] == "Alice"
    assert "author_url" not in fields


@pytest.mark.unit
def test_malformed_authors_entry_raises(tmp_path: Path) -> None:
    with pytest.raises(HaybaleTomlError, match=r"\[\[authors\]\]"):
        read_haybale_toml(_write(tmp_path, 'id = "core"\nauthors = ["Alice"]\n'))


# ── the raises ───────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(HaybaleTomlError, match="not found"):
        read_haybale_toml(tmp_path)


@pytest.mark.unit
def test_malformed_toml_raises_with_the_path(tmp_path: Path) -> None:
    d = _write(tmp_path, 'id = "core"\nlabel = [unclosed\n')
    with pytest.raises(HaybaleTomlError, match="Malformed TOML") as exc:
        read_haybale_toml(d)
    assert HAYBALE_TOML in str(exc.value)


@pytest.mark.unit
def test_missing_id_raises(tmp_path: Path) -> None:
    with pytest.raises(HaybaleTomlError, match="`id` is required"):
        read_haybale_toml(_write(tmp_path, 'label = "Core"\n'))


@pytest.mark.unit
def test_empty_id_raises(tmp_path: Path) -> None:
    with pytest.raises(HaybaleTomlError, match="`id` is required"):
        read_haybale_toml(_write(tmp_path, 'id = ""\n'))


@pytest.mark.unit
def test_missing_version_raises(tmp_path: Path) -> None:
    with pytest.raises(HaybaleTomlError, match="`version` is required"):
        read_haybale_toml(_write(tmp_path, 'id = "core"\n'))


@pytest.mark.unit
def test_empty_version_raises(tmp_path: Path) -> None:
    with pytest.raises(HaybaleTomlError, match="`version` is required"):
        read_haybale_toml(_write(tmp_path, 'id = "core"\nversion = ""\n'))


@pytest.mark.unit
def test_wrong_scalar_type_raises(tmp_path: Path) -> None:
    with pytest.raises(HaybaleTomlError, match="label must be a string"):
        read_haybale_toml(_write(tmp_path, 'id = "core"\nlabel = 3\n'))


@pytest.mark.unit
def test_wrong_list_type_raises(tmp_path: Path) -> None:
    with pytest.raises(HaybaleTomlError, match="must be a list of strings"):
        read_haybale_toml(_write(tmp_path, 'id = "core"\nlinked_libraries = "haybale_studio"\n'))


# ── linked_libraries must be module-shaped ───────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["haybale-studio", "haybale.studio", "haybale studio", "2cool"])
def test_non_module_linked_library_raises(tmp_path: Path, bad: str) -> None:
    """A hyphen yields the scope prefix "haybale-studio.", which matches no
    module — hot-reload then degrades silently. Reject it at read time."""
    d = _write(tmp_path, f'id = "core"\nlinked_libraries = ["{bad}"]\n')
    with pytest.raises(HaybaleTomlError, match="module names"):
        read_haybale_toml(d)


@pytest.mark.unit
def test_the_error_names_the_offending_entries(tmp_path: Path) -> None:
    d = _write(tmp_path, 'id = "core"\nlinked_libraries = ["haybale_ok", "haybale-bad"]\n')
    with pytest.raises(HaybaleTomlError) as exc:
        read_haybale_toml(d)
    assert "haybale-bad" in str(exc.value)
    assert "haybale_ok" not in str(exc.value)


# ── lenient sibling ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_lenient_returns_empty_instead_of_raising(tmp_path: Path) -> None:
    assert read_haybale_toml_lenient(tmp_path) == {}
    assert read_haybale_toml_lenient(_write(tmp_path, "id = [broken\n")) == {}


@pytest.mark.unit
def test_lenient_still_reads_a_good_file(tmp_path: Path) -> None:
    assert read_haybale_toml_lenient(_write(tmp_path, _FULL))["id"] == "core"


# ── derivations ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("dist", "expected"),
    [
        ("haybale-core", "haybale_core"),
        ("haybale-image-tools", "haybale_image_tools"),
        ("haybale_core", "haybale_core"),
        ("haybale.core", "haybale_core"),
        # PEP 503 lowercases the distribution name; [project] name keeps its
        # case. replace("-", "_") alone yields haybale_TEST_A — a directory that
        # does not exist.
        ("haybale-TEST_A", "haybale_test_a"),
    ],
)
def test_module_of_normalises_separators_and_case(dist: str, expected: str) -> None:
    assert module_of(dist) == expected


@pytest.mark.unit
def test_module_of_matches_every_in_tree_haybale() -> None:
    """The derivation is only sound if it agrees with what is on disk."""
    import tomllib

    barn = Path(__file__).resolve().parents[3] / "barn"
    checked = 0
    for lib_dir in sorted(barn.glob("haybale-*")):
        pyproject = lib_dir / "pyproject.toml"
        if not pyproject.is_file():
            continue
        name = tomllib.loads(pyproject.read_text())["project"]["name"]
        assert (lib_dir / module_of(name) / "__init__.py").is_file(), (
            f"{name}: module_of() -> {module_of(name)!r}, which is not the package dir"
        )
        checked += 1
    assert checked >= 5, "expected several in-tree haybales to check against"


@pytest.mark.unit
def test_tag_for_prefixes_v() -> None:
    assert tag_for("0.0.40") == "v0.0.40"


@pytest.mark.unit
def test_tag_for_does_not_double_the_prefix() -> None:
    """version is PEP 440 and never carries the v; if one shows up, it is a bug
    upstream and the tag should look wrong rather than silently right."""
    assert tag_for("v0.0.40") == "vv0.0.40"


# ── reading at the point of use ──────────────────────────────────────────────


@pytest.mark.unit
def test_read_haybale_reads_every_declared_field(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    row = read_haybale(
        _write(
            tmp_path,
            'name = "haybale-core"\n'
            'id = "core"\n'
            'version = "1.2.3"\n'
            'label = "Core"\n'
            'description = "d"\n'
            'tags = ["a", "b"]\n'
            'os = ["linux"]\n'
            'on_reload = "refresh"\n'
            'linked_libraries = ["haybale_studio"]\n'
            'origin = "https://github.test/o/r"\n'
            'origin_provider = "github"\n'
            'notes = "NOTES.md"\n'
            'examples_path = "examples/"\n'
            'tests_path = "tests/"\n'
            'homepage_url = "https://home.test"\n'
            'documentation_url = "https://docs.test"\n'
            'issues_url = "https://issues.test"\n'
            "[[authors]]\n"
            'name = "maybites"\n'
            'url = "https://maybites.ch"\n'
            "[[authors]]\n"
            'name = "cansik"\n',
        )
    )
    assert row.name == "haybale-core"
    assert row.id == "core"
    assert row.version == "1.2.3"
    assert row.label == "Core"
    assert row.description == "d"
    assert row.tags == ["a", "b"]
    assert row.os == ["linux"]
    assert row.on_reload == "refresh"
    assert row.linked_libraries == ["haybale_studio"]
    assert row.origin == "https://github.test/o/r"
    assert row.origin_provider == "github"
    assert row.notes == "NOTES.md"
    assert row.examples_path == "examples/"
    assert row.tests_path == "tests/"
    assert row.homepage_url == "https://home.test"
    assert row.documentation_url == "https://docs.test"
    assert row.issues_url == "https://issues.test"
    assert row.authors == [("maybites", "https://maybites.ch"), ("cansik", "")]


@pytest.mark.unit
def test_read_haybale_marks_source_local(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    row = read_haybale(_write(tmp_path, 'id = "core"\nversion = "1.0.0"\n'))
    assert row.source == "local"
    assert row.install_spec == ""
    assert row.stale is False
    assert row.via == ""


@pytest.mark.unit
def test_read_haybale_never_raises(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    assert read_haybale(tmp_path).name == ""  # no file at all
    assert read_haybale(_write(tmp_path, "id = [broken\n")).name == ""


@pytest.mark.unit
def test_read_haybale_drops_wrong_typed_values(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    row = read_haybale(_write(tmp_path, 'id = "core"\nlabel = 3\ntags = "nope"\nauthors = ["Alice"]\n'))
    assert row.label == ""
    assert row.tags == []
    assert row.authors == []


@pytest.mark.unit
def test_read_haybale_reads_deprecation(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    row = read_haybale(
        _write(
            tmp_path,
            'id = "core"\n[deprecated]\nsince = "1.0.0"\nreason = "old"\n',
        )
    )
    assert row.deprecated is not None
    assert row.deprecated.since == "1.0.0"
    assert row.deprecated.reason == "old"


@pytest.mark.unit
def test_read_haybale_reflects_edits(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    d = _write(tmp_path, 'id = "core"\ndescription = "before"\n')
    assert read_haybale(d).description == "before"
    _write(tmp_path, 'id = "core"\ndescription = "after"\n')
    assert read_haybale(d).description == "after"


# ── writing ───────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_write_authors_round_trips_through_read_haybale(tmp_path: Path) -> None:
    from haywire.core.library.haybale_toml import read_haybale, write_haybale_fields

    d = _write(tmp_path, 'id = "core"\nlabel = "Core"\n')
    write_haybale_fields(d, {"authors": [("maybites", "https://maybites.ch"), ("cansik", "")]})

    written = (d / HAYBALE_TOML).read_text()
    assert '[[authors]]\nname = "maybites"\nurl = "https://maybites.ch"' in written
    assert '[[authors]]\nname = "cansik"\n' in written
    assert "url" not in written.split("cansik")[1]  # no url = "" for the url-less author

    assert read_haybale(d).authors == [("maybites", "https://maybites.ch"), ("cansik", "")]


@pytest.mark.unit
def test_write_empty_authors_list_removes_the_key(tmp_path: Path) -> None:
    from haywire.core.library.haybale_toml import write_haybale_fields

    d = _write(
        tmp_path,
        'id = "core"\nlabel = "Core"\n\n[[authors]]\nname = "old"\n',
    )
    write_haybale_fields(d, {"authors": []})

    written = (d / HAYBALE_TOML).read_text()
    assert "authors" not in written


@pytest.mark.unit
def test_write_authors_preserves_comments_elsewhere_in_the_file(tmp_path: Path) -> None:
    """Comment-preserving like every other field write_haybale_fields makes."""
    from haywire.core.library.haybale_toml import write_haybale_fields

    d = _write(tmp_path, '# hand-written note\nid = "core"\nlabel = "Core"\n')
    write_haybale_fields(d, {"authors": [("alice", "")]})

    assert "# hand-written note" in (d / HAYBALE_TOML).read_text()


# ── version is projected into pyproject.toml ─────────────────────────────────


@pytest.mark.unit
def test_version_is_projected_into_pyproject():
    from haywire.core.publishing.generate import PROJECT_FIELDS

    assert PROJECT_FIELDS["version"] == "version"


@pytest.mark.unit
def test_sync_never_removes_the_pyproject_version(tmp_path):
    """pip reads version from pyproject and cannot read haybale.toml, so an
    absent declared version must leave the existing literal in place."""
    from haywire.core.publishing.generate import sync_pyproject_from_haybale

    module_dir = tmp_path / "haybale_alpha"
    module_dir.mkdir()
    (module_dir / "__init__.py").write_text("")
    _write(module_dir, 'id = "alpha"\ndescription = "d"\n')
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "1.2.3"\ndescription = "old"\n'
    )

    sync_pyproject_from_haybale(tmp_path)

    written = (tmp_path / "pyproject.toml").read_text()
    assert 'version = "1.2.3"' in written

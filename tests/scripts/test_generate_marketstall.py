"""Tests for scripts/generate_marketstall.py."""

from __future__ import annotations

from pathlib import Path

from typing import cast

import pytest

from scripts import generate_marketstall


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.unit
def test_generator_reads_the_decorator_through_the_shared_reader() -> None:
    """The local extract_library_metadata is gone; read_decorator replaces it.

    Its own behaviour is covered in tests/core/test_publishing/
    test_decorator_ast.py — this only pins that the generator uses it.
    """
    from haywire.core.publishing.manifest.decorator_ast import read_decorator

    fields = read_decorator(FIXTURE_DIR / "sample_marketstall_package_init.py")

    assert fields.label == "Alpha"
    # The fixture is an unmigrated library: `dependencies=` reaches
    # linked_libraries through the shim, as authored (no `_` -> `-`).
    assert fields.linked_libraries == ["haybale_beta"]


@pytest.mark.unit
def test_marketstall_config_reads_defaults_from_root_pyproject(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_marketstall_root_pyproject.toml").read_text())

    config = generate_marketstall.read_marketstall_config(root)

    assert config.source_url == "https://github.com/example/fake-workspace"
    assert config.docs_branch == "main"
    # No default_author: authors come from PEP 621 [project] authors, and the
    # fixture's leftover key is ignored rather than rejected.
    assert not hasattr(config, "default_author")
    assert config.default_tags == []
    # feed_base_url is optional in the fixture (defaults to empty); see the
    # generate-with-base-url test for the value-set path.
    assert config.feed_base_url == ""
    assert config.marketplace == ["haybale-alpha", "haybale-beta"]


@pytest.mark.unit
def test_build_entry_takes_pep621_fields_from_pyproject() -> None:
    pkg_pyproject = FIXTURE_DIR / "sample_marketstall_package_pyproject.toml"
    init_py = FIXTURE_DIR / "sample_marketstall_package_init.py"
    config = generate_marketstall.MarketstallConfig(
        source_url="https://github.com/example/fake-workspace",
        docs_branch="main",
        default_tags=[],
        feed_base_url="https://example.github.io/fake",
        marketplace=[],
    )

    entry = generate_marketstall.build_entry(
        pyproject_path=pkg_pyproject,
        init_py=init_py,
        config=config,
        subdirectory="subdir-a/haybale-alpha",
        module_name="haybale_alpha",
    )

    assert entry["name"] == "haybale-alpha"
    # label is the one row field still authored on the decorator.
    assert entry["label"] == "Alpha"
    assert entry["version"] == "0.0.3"
    # pyproject wins for description: the decorator stopped accepting the kwarg
    # when the distribution plan landed. The fixture still authors one (it is an
    # unmigrated library) and it is correctly ignored.
    assert entry["description"] == "Alpha library — does alpha things"
    assert entry["source"] == "pypi"
    assert entry["install_spec"] == "haybale-alpha"
    # keywords/authors are absent from this fixture's pyproject, and to_dict()
    # omits empty values rather than emitting them.
    assert "tags" not in entry
    assert "authors" not in entry
    # From the decorator, as authored — NOT from pyproject's haybale-* deps,
    # which is where this field used to come from.
    assert entry["linked_libraries"] == ["haybale_beta"]
    assert entry["origin"] == "https://github.com/example/fake-workspace"
    # A path from the git root, not a URL — the consumer resolves it against
    # `origin` at `install_spec`'s ref. Trailing slash marks a directory.
    assert entry["docs_path"] == "subdir-a/haybale-alpha/haybale_alpha/"


@pytest.mark.unit
def test_build_entry_emits_git_source_with_subdirectory_install_spec() -> None:
    pkg_pyproject = FIXTURE_DIR / "sample_marketstall_package_pyproject.toml"
    init_py = FIXTURE_DIR / "sample_marketstall_package_init.py"
    config = generate_marketstall.MarketstallConfig(
        source_url="https://github.com/example/fake-workspace",
        docs_branch="main",
        default_tags=[],
        feed_base_url="https://example.github.io/fake",
        marketplace=[],
    )

    entry = generate_marketstall.build_entry(
        pyproject_path=pkg_pyproject,
        init_py=init_py,
        config=config,
        subdirectory="subdir-a/haybale-alpha",
        module_name="haybale_alpha",
        source="git",
    )

    assert entry["source"] == "git"
    assert entry["install_spec"] == (
        "haybale-alpha @ git+https://github.com/example/fake-workspace.git"
        "#subdirectory=subdir-a/haybale-alpha"
    )


@pytest.mark.unit
def test_build_entry_falls_back_to_pyproject_description_when_decorator_absent(tmp_path: Path) -> None:
    pkg_pyproject = tmp_path / "pyproject.toml"
    pkg_pyproject.write_text(
        "[project]\n"
        'name = "haybale-bare"\n'
        'version = "0.0.1"\n'
        'description = "Bare-bones package without an @library decorator."\n'
        "dependencies = []\n"
    )
    init_py = tmp_path / "haybale_bare" / "__init__.py"
    init_py.parent.mkdir()
    init_py.write_text('"""no decorator."""\n')
    config = generate_marketstall.MarketstallConfig(
        source_url="https://github.com/example/fake-workspace",
        docs_branch="main",
        default_tags=["default-tag"],
        feed_base_url="https://example.github.io/fake",
        marketplace=[],
    )

    entry = generate_marketstall.build_entry(
        pyproject_path=pkg_pyproject,
        init_py=init_py,
        config=config,
        subdirectory="barn/haybale-bare",
        module_name="haybale_bare",
    )

    assert entry["label"] == "haybale-bare"  # falls back to name
    assert entry["description"] == "Bare-bones package without an @library decorator."
    # No [project] authors and no keywords: authors is omitted entirely (the
    # config default_author is no longer substituted — an unauthored field is
    # reported absent), while default_tags still backfills tags.
    assert "authors" not in entry
    assert entry["tags"] == ["default-tag"]  # config default
    assert "linked_libraries" not in entry


@pytest.mark.unit
def test_emit_stall_toml_round_trips_via_tomllib() -> None:
    entry = {
        "name": "haybale-alpha",
        "label": "Alpha",
        "version": "0.0.3",
        "description": "alpha desc",
        "authors": ["Alpha Author"],
        "source": "pypi",
        "install_spec": "haybale-alpha",
        "tags": ["a", "b"],
        "linked_libraries": ["haybale-beta"],
        "origin": "https://github.com/example/fake-workspace",
        "docs_path": "x/y/",
    }

    out_text = generate_marketstall.emit_stall_toml(cast(dict, entry))
    import tomllib

    parsed = tomllib.loads(out_text)

    # Per spec §11.3 every stall has exactly one [[haybales]] entry, under the
    # new vocabulary (not legacy [[packages]]).
    assert "packages" not in parsed
    assert len(parsed["haybales"]) == 1
    assert parsed["haybales"][0]["name"] == "haybale-alpha"
    assert parsed["haybales"][0]["linked_libraries"] == ["haybale-beta"]


@pytest.mark.unit
def test_emit_stall_toml_includes_name_in_header() -> None:
    """Each generated stall file's comment header should mention the dist name
    so a human reader can identify it without parsing TOML."""
    entry = {
        "name": "haybale-x",
        "version": "0.0.1",
        "label": "X",
        "description": "d",
        "authors": ["a"],
        "source": "pypi",
        "install_spec": "haybale-x",
        "tags": [],
        "linked_libraries": [],
        "origin": "u",
        "docs_path": "d2",
    }
    out = generate_marketstall.emit_stall_toml(cast(dict, entry))
    assert out.startswith("# Marketstall for haybale-x")


@pytest.mark.unit
def test_emit_marketplace_toml_writes_one_stall_per_url() -> None:
    """The aggregator (spec §11.2) holds one [[stalls]] entry per URL, each
    with empty ignores/doubles/blocked arrays (consumers populate those)."""
    out = generate_marketstall.emit_marketplace_toml(
        [
            "https://example.github.io/feed/stalls/haybale-a.toml",
            "https://example.github.io/feed/stalls/haybale-b.toml",
        ]
    )
    import tomllib

    parsed = tomllib.loads(out)
    assert "haybales" not in parsed  # aggregator carries no inline haybales here
    assert len(parsed["stalls"]) == 2
    assert parsed["stalls"][0]["url"] == "https://example.github.io/feed/stalls/haybale-a.toml"
    for sub in parsed["stalls"]:
        assert sub["ignores"] == []
        assert sub["doubles"] == []
        assert sub["blocked"] == []


@pytest.mark.unit
def test_emit_marketplace_toml_starts_with_header_comment() -> None:
    out = generate_marketstall.emit_marketplace_toml([])
    assert out.startswith("# Official haywire marketplace")


@pytest.mark.unit
def test_emit_stall_toml_escapes_quotes_in_strings() -> None:
    entry = {
        "name": "haybale-x",
        "label": 'X with "quotes"',
        "version": "0.0.1",
        "description": "desc",
        "authors": ["Author"],
        "source": "pypi",
        "install_spec": "haybale-x",
        "tags": [],
        "linked_libraries": [],
        "origin": "u",
        "docs_path": "d",
    }
    out = generate_marketstall.emit_stall_toml(cast(dict, entry))
    import tomllib

    parsed = tomllib.loads(out)
    assert parsed["haybales"][0]["label"] == 'X with "quotes"'


@pytest.mark.unit
def test_emit_stall_toml_escapes_control_characters() -> None:
    """A description containing a newline must still produce valid round-trippable TOML."""
    entry = {
        "name": "haybale-multi",
        "label": "Multi",
        "version": "0.0.1",
        "description": "Line one.\nLine two with a tab\there.",
        "authors": ["Author"],
        "source": "pypi",
        "install_spec": "haybale-multi",
        "tags": [],
        "linked_libraries": [],
        "origin": "u",
        "docs_path": "d",
    }
    out = generate_marketstall.emit_stall_toml(cast(dict, entry))
    import tomllib

    parsed = tomllib.loads(out)
    assert parsed["haybales"][0]["description"] == "Line one.\nLine two with a tab\there."


@pytest.mark.unit
def test_generate_walks_publish_order_and_returns_toml(tmp_path: Path) -> None:
    # Build a mini workspace with 2 publishable packages on disk.
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_marketstall_root_pyproject.toml").read_text())

    alpha = tmp_path / "subdir-a/haybale-alpha"
    alpha.mkdir(parents=True)
    (alpha / "pyproject.toml").write_text(
        (FIXTURE_DIR / "sample_marketstall_package_pyproject.toml").read_text()
    )
    (alpha / "haybale_alpha").mkdir()
    (alpha / "haybale_alpha" / "__init__.py").write_text(
        (FIXTURE_DIR / "sample_marketstall_package_init.py").read_text()
    )

    beta = tmp_path / "subdir-a/haybale-beta"
    beta.mkdir(parents=True)
    (beta / "pyproject.toml").write_text(
        "[project]\n"
        'name = "haybale-beta"\n'
        'version = "0.0.3"\n'
        'description = "Beta library"\n'
        "dependencies = []\n"
    )
    (beta / "haybale_beta").mkdir()
    (beta / "haybale_beta" / "__init__.py").write_text('"""beta."""\n')

    # haybale-internal is in lockstep_unpublished — must NOT appear in output.
    internal = tmp_path / "subdir-b/haybale-internal"
    internal.mkdir(parents=True)
    (internal / "pyproject.toml").write_text(
        '[project]\nname = "haybale-internal"\nversion = "0.0.3"\ndescription = "i"\ndependencies = []\n'
    )

    result = generate_marketstall.generate(root, feed_base_url="https://feed.example/haywire")

    import tomllib

    # Stalls: one per publish_order entry, in publish order.
    assert [dist for dist, _body in result.stalls] == ["haybale-alpha", "haybale-beta"]
    alpha_parsed = tomllib.loads(result.stalls[0][1])
    assert alpha_parsed["haybales"][0]["name"] == "haybale-alpha"
    assert alpha_parsed["haybales"][0]["version"] == "0.0.3"
    assert alpha_parsed["haybales"][0]["docs_path"] == "subdir-a/haybale-alpha/haybale_alpha/"

    # Aggregator: one [[stalls]] per dist, URLs composed under feed_base_url.
    mp_parsed = tomllib.loads(result.marketplace_toml)
    assert [s["url"] for s in mp_parsed["stalls"]] == [
        "https://feed.example/haywire/stalls/haybale-alpha.toml",
        "https://feed.example/haywire/stalls/haybale-beta.toml",
    ]


@pytest.mark.unit
def test_generate_resolves_module_path_from_entry_points(tmp_path: Path) -> None:
    """When pyproject has a [project.entry-points."haywire.libraries"] block, infer module
    name from there. Otherwise fall back to the package directory name with hyphens → underscores."""
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        '[tool.haywire.release]\npip_publish_order = ["haybale-foo"]\n'
        "git_publish_order = []\nlockstep_unpublished = []\n"
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/fake-workspace"\n'
        'docs_branch = "main"\n'
        "default_tags = []\n"
        'marketplace = ["haybale-foo"]\n'
    )
    pkg = tmp_path / "pkgs/haybale-foo"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.0.1"\ndescription = "d"\ndependencies = []\n'
        '[project.entry-points."haywire.libraries"]\nfoo = "haybale_foo_renamed:Library"\n'
    )
    (pkg / "haybale_foo_renamed").mkdir()
    (pkg / "haybale_foo_renamed" / "__init__.py").write_text('"""foo."""\n')

    import tomllib

    result = generate_marketstall.generate(root, feed_base_url="https://feed.example/x")
    stall_parsed = tomllib.loads(result.stalls[0][1])
    assert stall_parsed["haybales"][0]["docs_path"] == "pkgs/haybale-foo/haybale_foo_renamed/"


@pytest.mark.unit
def test_generate_resolves_src_layout_via_hatch_packages(tmp_path: Path) -> None:
    """src-layout packages declare [tool.hatch.build.targets.wheel].packages = ["src/module"].
    The generator must read that field to find the right module path."""
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        '[tool.haywire.release]\npip_publish_order = ["haywire-frame"]\n'
        "git_publish_order = []\nlockstep_unpublished = []\n"
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        "default_tags = []\n"
        "marketplace = []\n"
    )
    pkg = tmp_path / "pkgs/haywire-frame"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        "[project]\n"
        'name = "haywire-frame"\n'
        'version = "0.0.1"\n'
        'description = "framework"\n'
        "dependencies = []\n"
        "[tool.hatch.build.targets.wheel]\n"
        'packages = ["src/haywire"]\n'
    )
    # Module lives behind src/.
    (pkg / "src" / "haywire").mkdir(parents=True)
    (pkg / "src" / "haywire" / "__init__.py").write_text('"""haywire framework module."""\n')

    import tomllib

    result = generate_marketstall.generate(root, feed_base_url="https://feed.example/x")
    # haywire-frame is a framework package — not in marketplace, not in the feed.
    assert result.stalls == []
    mp = tomllib.loads(result.marketplace_toml)
    assert mp.get("stalls", []) == []


@pytest.mark.unit
def test_generate_tolerates_missing_init_py(tmp_path: Path) -> None:
    """A package whose pyproject describes a module that doesn't have an __init__.py
    at the expected path should still generate an entry — read_decorator returns
    all-defaults for a missing file, so the row is built from pyproject plus
    config defaults."""
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        '[tool.haywire.release]\npip_publish_order = ["haybale-ghost"]\n'
        "git_publish_order = []\nlockstep_unpublished = []\n"
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        'default_tags = ["default-tag"]\n'
        'marketplace = ["haybale-ghost"]\n'
    )
    pkg = tmp_path / "pkgs/haybale-ghost"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "haybale-ghost"\nversion = "0.0.1"\ndescription = "no init"\ndependencies = []\n'
    )
    # No haybale_ghost/__init__.py on disk.

    import tomllib

    result = generate_marketstall.generate(root, feed_base_url="https://feed.example/x")
    stall_parsed = tomllib.loads(result.stalls[0][1])
    entry = stall_parsed["haybales"][0]
    assert entry["name"] == "haybale-ghost"
    assert entry["description"] == "no init"  # pyproject fallback
    assert "authors" not in entry  # no [project] authors, and no repo-wide default
    assert entry["tags"] == ["default-tag"]  # config default
    assert entry["label"] == "haybale-ghost"  # name fallback


@pytest.mark.unit
def test_generate_requires_feed_base_url(tmp_path: Path) -> None:
    """If neither the pyproject nor the CLI provides a feed_base_url, the
    generator can't compose [[stalls]] URLs and must fail loudly rather than
    emit broken subscription URLs (spec §11)."""
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        "[tool.haywire.release]\npip_publish_order = []\ngit_publish_order = []\nlockstep_unpublished = []\n"
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        "default_tags = []\n"
        "marketplace = []\n"
        # NOTE: no feed_base_url set
    )

    with pytest.raises(ValueError, match="feed_base_url"):
        generate_marketstall.generate(root)


@pytest.mark.unit
def test_cli_writes_marketplace_and_stalls_to_out_dir(tmp_path: Path) -> None:
    """End-to-end: main() writes <out-dir>/marketplace.toml plus one
    <out-dir>/stalls/<dist>.toml per publish_order entry."""
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_marketstall_root_pyproject.toml").read_text())

    alpha = tmp_path / "subdir-a/haybale-alpha"
    alpha.mkdir(parents=True)
    (alpha / "pyproject.toml").write_text(
        (FIXTURE_DIR / "sample_marketstall_package_pyproject.toml").read_text()
    )
    (alpha / "haybale_alpha").mkdir()
    (alpha / "haybale_alpha" / "__init__.py").write_text(
        (FIXTURE_DIR / "sample_marketstall_package_init.py").read_text()
    )

    beta = tmp_path / "subdir-a/haybale-beta"
    beta.mkdir(parents=True)
    (beta / "pyproject.toml").write_text(
        '[project]\nname = "haybale-beta"\nversion = "0.0.3"\ndescription = "b"\ndependencies = []\n'
    )
    (beta / "haybale_beta").mkdir()
    (beta / "haybale_beta" / "__init__.py").write_text('"""beta."""\n')

    # lockstep_unpublished entry must exist on disk per locate_packages, even
    # though it won't appear in the generated output (publish_order only).
    internal = tmp_path / "subdir-b/haybale-internal"
    internal.mkdir(parents=True)
    (internal / "pyproject.toml").write_text(
        '[project]\nname = "haybale-internal"\nversion = "0.0.3"\ndescription = "i"\ndependencies = []\n'
    )

    out_dir = tmp_path / "out"
    rc = generate_marketstall.main(
        [
            "--root",
            str(root),
            "--out-dir",
            str(out_dir),
            "--feed-base-url",
            "https://feed.example/haywire",
        ]
    )
    assert rc == 0

    # Both top-level marketplace and per-stall files exist:
    assert (out_dir / "marketplace.toml").is_file()
    assert (out_dir / "stalls" / "haybale-alpha.toml").is_file()
    assert (out_dir / "stalls" / "haybale-beta.toml").is_file()

    import tomllib

    mp = tomllib.loads((out_dir / "marketplace.toml").read_text())
    assert [s["url"] for s in mp["stalls"]] == [
        "https://feed.example/haywire/stalls/haybale-alpha.toml",
        "https://feed.example/haywire/stalls/haybale-beta.toml",
    ]
    alpha_parsed = tomllib.loads((out_dir / "stalls" / "haybale-alpha.toml").read_text())
    assert alpha_parsed["haybales"][0]["name"] == "haybale-alpha"


@pytest.mark.unit
def test_generate_errors_when_marketplace_entry_not_in_any_publish_list(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        "[tool.haywire.release]\n"
        'pip_publish_order = ["haybale-alpha"]\n'
        "git_publish_order = []\n"
        "lockstep_unpublished = []\n"
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        "default_tags = []\n"
        'marketplace = ["haybale-alpha", "haybale-unknown"]\n'
    )
    pkg = tmp_path / "pkgs/haybale-alpha"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.0.1"\ndescription = "d"\ndependencies = []\n'
    )
    (pkg / "haybale_alpha").mkdir()
    (pkg / "haybale_alpha" / "__init__.py").write_text('"""alpha."""\n')

    with pytest.raises(ValueError, match="haybale-unknown"):
        generate_marketstall.generate(root, feed_base_url="https://feed.example/x")


@pytest.mark.unit
def test_generate_errors_when_package_in_both_publish_lists(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        "[tool.haywire.release]\n"
        'pip_publish_order = ["haybale-alpha"]\n'
        'git_publish_order = ["haybale-alpha"]\n'
        "lockstep_unpublished = []\n"
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        "default_tags = []\n"
        'marketplace = ["haybale-alpha"]\n'
    )
    pkg = tmp_path / "pkgs/haybale-alpha"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.0.1"\ndescription = "d"\ndependencies = []\n'
    )
    (pkg / "haybale_alpha").mkdir()
    (pkg / "haybale_alpha" / "__init__.py").write_text('"""alpha."""\n')

    with pytest.raises(ValueError, match="haybale-alpha"):
        generate_marketstall.generate(root, feed_base_url="https://feed.example/x")


def _config(**overrides) -> generate_marketstall.MarketstallConfig:
    """A MarketstallConfig with the fields these tests don't care about filled in."""
    base = dict(
        source_url="https://github.com/o/r",
        docs_branch="main",
        default_tags=[],
        feed_base_url="https://example.github.io/fake",
        marketplace=[],
    )
    base.update(overrides)
    return generate_marketstall.MarketstallConfig(**base)  # type: ignore[arg-type]


def _demo_library(tmp_path: Path, *, pyproject: str, decorator: str) -> tuple[Path, Path]:
    """Write a one-library fixture; return (pyproject_path, init_py)."""
    lib = tmp_path / "barn" / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "pyproject.toml").write_text(pyproject)
    (lib / "haybale_demo" / "__init__.py").write_text(decorator)
    return lib / "pyproject.toml", lib / "haybale_demo" / "__init__.py"


@pytest.mark.unit
def test_linked_libraries_come_from_the_decorator_not_pyproject(tmp_path: Path) -> None:
    """The CI generator used to fill this from pyproject's haybale-* deps.

    The share pipeline reads the decorator. Same field, two inputs — a
    divergence that only showed up when comparing published feeds.
    """
    pyproject_path, init_py = _demo_library(
        tmp_path,
        pyproject=(
            '[project]\nname = "haybale-demo"\nversion = "0.1.0"\n'
            'description = "From pyproject"\n'
            'dependencies = ["haybale-other>=1.0", "haywire-core>=0.0.40"]\n'
        ),
        decorator=(
            '@library(\n    id="demo",\n    label="Demo",\n'
            '    linked_libraries=["haybale_studio"],\n)\nclass Library: ...\n'
        ),
    )

    entry = generate_marketstall.build_entry(
        pyproject_path=pyproject_path,
        init_py=init_py,
        config=_config(),
        subdirectory="barn/haybale-demo",
        module_name="haybale_demo",
    )

    assert entry["linked_libraries"] == ["haybale_studio"]
    assert "haybale-other" not in cast(list, entry.get("linked_libraries", []))


@pytest.mark.unit
def test_description_and_tags_come_from_pyproject(tmp_path: Path) -> None:
    """Precedence is pyproject, not the decorator — the decorator no longer
    accepts description= at all since the distribution plan landed."""
    pyproject_path, init_py = _demo_library(
        tmp_path,
        pyproject=(
            '[project]\nname = "haybale-demo"\nversion = "0.1.0"\n'
            'description = "From pyproject"\nkeywords = ["a", "b"]\n'
            'authors = [{name = "Author One"}]\n'
        ),
        decorator='@library(id="demo", label="Demo")\nclass Library: ...\n',
    )

    entry = generate_marketstall.build_entry(
        pyproject_path=pyproject_path,
        init_py=init_py,
        config=_config(),
        subdirectory="barn/haybale-demo",
        module_name="haybale_demo",
    )

    assert entry["description"] == "From pyproject"
    assert entry["tags"] == ["a", "b"]
    assert entry["authors"] == ["Author One"]


@pytest.mark.unit
def test_os_and_paths_reach_the_row(tmp_path: Path) -> None:
    """Fields the hand-assembled dict dropped entirely before this plan."""
    pyproject_path, init_py = _demo_library(
        tmp_path,
        pyproject='[project]\nname = "haybale-demo"\nversion = "0.1.0"\n',
        decorator=(
            '@library(\n    id="demo",\n    label="Demo",\n'
            '    os=["macos"],\n    on_reload="restart",\n'
            '    examples_path="examples/OVERVIEW.md",\n)\nclass Library: ...\n'
        ),
    )

    entry = generate_marketstall.build_entry(
        pyproject_path=pyproject_path,
        init_py=init_py,
        config=_config(),
        subdirectory="barn/haybale-demo",
        module_name="haybale_demo",
    )

    assert entry["os"] == ["macos"]
    assert entry["on_reload"] == "restart"
    assert entry["examples_path"] == "barn/haybale-demo/examples/OVERVIEW.md"


@pytest.mark.unit
def test_both_producers_emit_the_same_row_for_one_library(tmp_path: Path) -> None:
    """The share pipeline and the CI generator differ only in documented ways.

    They disagreed on two fields before this plan: linked_libraries came from
    pyproject in one and the decorator in the other, and description/tags
    preferred the decorator in one and pyproject in the other. Nothing but a
    test stops them drifting apart again — the two live in different packages
    and neither imports the other's row builder.
    """
    from haywire.core.publishing.marketstall import _build_entry_for_library

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    lib = repo / "barn" / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-demo"\nversion = "0.1.0"\n'
        'description = "Shared"\nkeywords = ["k"]\n'
        'authors = [{name = "A"}]\n'
    )
    (lib / "haybale_demo" / "__init__.py").write_text(
        '@library(\n    id="demo",\n    label="Demo",\n'
        '    linked_libraries=["haybale_studio"],\n    os=["macos"],\n'
        '    examples_path="examples/OVERVIEW.md",\n)\n'
        "class Library: ...\n"
    )

    ci = generate_marketstall.build_entry(
        pyproject_path=lib / "pyproject.toml",
        init_py=lib / "haybale_demo" / "__init__.py",
        config=_config(),
        subdirectory="barn/haybale-demo",
        module_name="haybale_demo",
    )
    share = _build_entry_for_library(lib)
    assert share is not None

    # source and install_spec differ by design: PyPI vs git, and the CI
    # generator resolves refs against a branch because it has no tag context.
    # origin differs too — the share pipeline reads it from the git remote.
    shared = {
        "label",
        "version",
        "description",
        "tags",
        "authors",
        "linked_libraries",
        "os",
        "docs_path",
        "examples_path",
    }
    for key in shared:
        assert ci.get(key) == share.get(key), key

"""Tests for scripts/generate_marketstall.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import generate_marketstall


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.unit
def test_extract_library_metadata_reads_decorator_fields() -> None:
    init_py = FIXTURE_DIR / "sample_marketstall_package_init.py"

    meta = generate_marketstall.extract_library_metadata(init_py)

    assert meta.label == "Alpha"
    assert meta.author == "Alpha Author"
    assert meta.tags == ["alpha", "demo"]
    assert meta.description == "Alpha library — overridden in pyproject? Decorator wins."


@pytest.mark.unit
def test_extract_library_metadata_returns_none_fields_when_decorator_missing(tmp_path: Path) -> None:
    # Plain module with no @library call.
    plain = tmp_path / "plain_init.py"
    plain.write_text('"""no decorator here."""\n')

    meta = generate_marketstall.extract_library_metadata(plain)

    assert meta.label is None
    assert meta.author is None
    assert meta.tags is None
    assert meta.description is None


@pytest.mark.unit
def test_marketstall_config_reads_defaults_from_root_pyproject(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_marketstall_root_pyproject.toml").read_text())

    config = generate_marketstall.read_marketstall_config(root)

    assert config.source_url == "https://github.com/example/fake-workspace"
    assert config.docs_branch == "main"
    assert config.default_author == "Fake Team"
    assert config.default_tags == []
    # feed_base_url is optional in the fixture (defaults to empty); see the
    # generate-with-base-url test for the value-set path.
    assert config.feed_base_url == ""


@pytest.mark.unit
def test_build_entry_uses_decorator_values_over_pyproject() -> None:
    pkg_pyproject = FIXTURE_DIR / "sample_marketstall_package_pyproject.toml"
    init_py = FIXTURE_DIR / "sample_marketstall_package_init.py"
    config = generate_marketstall.MarketstallConfig(
        source_url="https://github.com/example/fake-workspace",
        docs_branch="main",
        default_author="Fake Team",
        default_tags=[],
        feed_base_url="https://example.github.io/fake",
    )

    entry = generate_marketstall.build_entry(
        pyproject_path=pkg_pyproject,
        init_py=init_py,
        config=config,
        subdirectory="subdir-a/haybale-alpha",
        module_name="haybale_alpha",
    )

    assert entry["name"] == "haybale-alpha"
    assert entry["label"] == "Alpha"
    assert entry["min_version"] == "0.0.3"
    # Decorator overrides pyproject for description:
    assert entry["description"] == "Alpha library — overridden in pyproject? Decorator wins."
    assert entry["author"] == "Alpha Author"
    assert entry["source"] == "pypi"
    assert entry["install_spec"] == "haybale-alpha"
    assert entry["tags"] == ["alpha", "demo"]
    # Only haybale-* siblings; haywire-core and external-lib are filtered out:
    assert entry["dependencies"] == ["haybale-beta"]
    assert entry["source_url"] == "https://github.com/example/fake-workspace"
    assert entry["docs_url"] == (
        "https://raw.githubusercontent.com/example/fake-workspace/main/subdir-a/haybale-alpha/haybale_alpha/"
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
        default_author="Fake Team",
        default_tags=["default-tag"],
        feed_base_url="https://example.github.io/fake",
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
    assert entry["author"] == "Fake Team"  # config default
    assert entry["tags"] == ["default-tag"]  # config default
    assert entry["dependencies"] == []


@pytest.mark.unit
def test_emit_stall_toml_round_trips_via_tomllib() -> None:
    entry = {
        "name": "haybale-alpha",
        "label": "Alpha",
        "min_version": "0.0.3",
        "description": "alpha desc",
        "author": "Alpha Author",
        "source": "pypi",
        "install_spec": "haybale-alpha",
        "tags": ["a", "b"],
        "dependencies": ["haybale-beta"],
        "source_url": "https://github.com/example/fake-workspace",
        "docs_url": "https://raw.githubusercontent.com/example/fake-workspace/main/x/y/",
    }

    out_text = generate_marketstall.emit_stall_toml(entry)
    import tomllib

    parsed = tomllib.loads(out_text)

    # Per spec §11.3 every stall has exactly one [[haybales]] entry, under the
    # new vocabulary (not legacy [[packages]]).
    assert "packages" not in parsed
    assert len(parsed["haybales"]) == 1
    assert parsed["haybales"][0]["name"] == "haybale-alpha"
    assert parsed["haybales"][0]["dependencies"] == ["haybale-beta"]


@pytest.mark.unit
def test_emit_stall_toml_includes_name_in_header() -> None:
    """Each generated stall file's comment header should mention the dist name
    so a human reader can identify it without parsing TOML."""
    entry = {
        "name": "haybale-x",
        "min_version": "0.0.1",
        "label": "X",
        "description": "d",
        "author": "a",
        "source": "pypi",
        "install_spec": "haybale-x",
        "tags": [],
        "dependencies": [],
        "source_url": "u",
        "docs_url": "d2",
    }
    out = generate_marketstall.emit_stall_toml(entry)
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
        "min_version": "0.0.1",
        "description": "desc",
        "author": "Author",
        "source": "pypi",
        "install_spec": "haybale-x",
        "tags": [],
        "dependencies": [],
        "source_url": "u",
        "docs_url": "d",
    }
    out = generate_marketstall.emit_stall_toml(entry)
    import tomllib

    parsed = tomllib.loads(out)
    assert parsed["haybales"][0]["label"] == 'X with "quotes"'


@pytest.mark.unit
def test_emit_stall_toml_escapes_control_characters() -> None:
    """A description containing a newline must still produce valid round-trippable TOML."""
    entry = {
        "name": "haybale-multi",
        "label": "Multi",
        "min_version": "0.0.1",
        "description": "Line one.\nLine two with a tab\there.",
        "author": "Author",
        "source": "pypi",
        "install_spec": "haybale-multi",
        "tags": [],
        "dependencies": [],
        "source_url": "u",
        "docs_url": "d",
    }
    out = generate_marketstall.emit_stall_toml(entry)
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
    assert alpha_parsed["haybales"][0]["min_version"] == "0.0.3"
    assert alpha_parsed["haybales"][0]["docs_url"].endswith("/subdir-a/haybale-alpha/haybale_alpha/")

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
        '[tool.haywire.release]\npublish_order = ["haybale-foo"]\nlockstep_unpublished = []\n'
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/fake-workspace"\n'
        'docs_branch = "main"\n'
        'default_author = ""\n'
        "default_tags = []\n"
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
    assert stall_parsed["haybales"][0]["docs_url"].endswith("/pkgs/haybale-foo/haybale_foo_renamed/")


@pytest.mark.unit
def test_generate_resolves_src_layout_via_hatch_packages(tmp_path: Path) -> None:
    """src-layout packages declare [tool.hatch.build.targets.wheel].packages = ["src/module"].
    The generator must read that field to find the right module path."""
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        '[tool.haywire.release]\npublish_order = ["haywire-frame"]\nlockstep_unpublished = []\n'
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        'default_author = "Team"\n'
        "default_tags = []\n"
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
    stall_parsed = tomllib.loads(result.stalls[0][1])
    entry = stall_parsed["haybales"][0]
    assert entry["name"] == "haywire-frame"
    # docs_url uses just the module name, not the src/ prefix:
    assert entry["docs_url"].endswith("/pkgs/haywire-frame/haywire/")


@pytest.mark.unit
def test_generate_tolerates_missing_init_py(tmp_path: Path) -> None:
    """A package whose pyproject describes a module that doesn't have an __init__.py
    at the expected path should still generate an entry (with all-None decorator fields,
    falling back to pyproject description + config defaults)."""
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        '[tool.haywire.release]\npublish_order = ["haybale-ghost"]\nlockstep_unpublished = []\n'
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        'default_author = "Default Author"\n'
        'default_tags = ["default-tag"]\n'
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
    assert entry["author"] == "Default Author"  # config default
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
        "[tool.haywire.release]\npublish_order = []\nlockstep_unpublished = []\n"
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        'default_author = ""\n'
        "default_tags = []\n"
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

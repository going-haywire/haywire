"""Tests for scripts/generate_marketstall.py."""

from __future__ import annotations

from pathlib import Path

from typing import cast

import pytest

from scripts import generate_marketstall


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _write_package(
    pkg_dir: Path,
    *,
    name: str,
    version: str = "0.0.1",
    module_name: str | None = None,
    dependencies: list[str] | None = None,
    haybale_toml: str | None = None,
) -> None:
    """Write a minimal barn-shaped package: pyproject.toml + <module>/haybale.toml.

    Mirrors what `_build_entry_for_library` (the shared builder) actually
    reads: name/version fall back to `pyproject.toml` only when absent from
    `haybale.toml`, and everything descriptive comes from `haybale.toml`.
    `haybale_toml`, when given, is written verbatim; otherwise a small
    default with label/description/tags/authors is used so callers get a
    non-empty row without repeating that boilerplate everywhere.
    """
    module_name = module_name or name.replace("-", "_")
    pkg_dir.mkdir(parents=True, exist_ok=True)
    deps_toml = ", ".join(f'"{d}"' for d in (dependencies or []))
    (pkg_dir / "pyproject.toml").write_text(
        "[project]\n"
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        f'description = "{name} description"\n'
        f"dependencies = [{deps_toml}]\n"
    )
    module_dir = pkg_dir / module_name
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text('"""package init."""\n')
    (module_dir / "haybale.toml").write_text(
        haybale_toml
        if haybale_toml is not None
        else (
            f'name = "{name}"\n'
            f'id = "{name.removeprefix("haybale-")}"\n'
            f'version = "{version}"\n'
            f'label = "{name.title()}"\n'
            f'description = "{name} description"\n'
            'tags = ["demo"]\n'
            "\n"
            "[[authors]]\n"
            'name = "Test Author"\n'
        )
    )


@pytest.mark.unit
def test_marketstall_config_reads_defaults_from_root_pyproject(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_marketstall_root_pyproject.toml").read_text())

    config = generate_marketstall.read_marketstall_config(root)

    assert config.source_url == "https://github.com/example/fake-workspace"
    assert config.docs_branch == "main"
    # feed_base_url is optional in the fixture (defaults to empty); see the
    # generate-with-base-url test for the value-set path.
    assert config.feed_base_url == ""
    assert config.marketplace == ["haybale-alpha", "haybale-beta"]


@pytest.mark.unit
def test_build_entry_uses_haybale_toml_over_pyproject(tmp_path: Path) -> None:
    """label/description/tags/authors come from haybale.toml, not pyproject."""
    pkg_dir = tmp_path / "haybale-alpha"
    _write_package(
        pkg_dir,
        name="haybale-alpha",
        version="0.0.3",
        dependencies=["haywire-core>=0.0.3", "haybale-beta>=0.0.3", "external-lib>=1.0"],
        haybale_toml=(
            'name = "haybale-alpha"\n'
            'id = "alpha"\n'
            'version = "0.0.3"\n'
            'label = "Alpha"\n'
            'description = "Alpha library — declared in haybale.toml."\n'
            'tags = ["alpha", "demo"]\n'
            "\n"
            "[[authors]]\n"
            'name = "Alpha Author"\n'
        ),
    )

    entry = generate_marketstall.build_entry(pkg_dir)

    assert entry["name"] == "haybale-alpha"
    assert entry["id"] == "alpha"
    assert entry["label"] == "Alpha"
    assert entry["version"] == "0.0.3"
    assert entry["description"] == "Alpha library — declared in haybale.toml."
    assert entry["source"] == "pypi"
    assert entry["install_spec"] == "haybale-alpha"
    assert entry["tags"] == ["alpha", "demo"]
    assert entry["authors"] == [{"name": "Alpha Author"}]
    # No decorator-era keys survive:
    assert "author" not in entry
    assert "dependencies" not in entry
    assert "source_url" not in entry
    assert "docs_url" not in entry


@pytest.mark.unit
def test_build_entry_emits_git_source_with_subdirectory_install_spec(tmp_path: Path) -> None:
    """Libraries in git_publish_order keep the builder's own git+subdirectory
    install_spec — the script only overrides install_spec for source="pypi"."""
    pkg_dir = tmp_path / "haybale-alpha"
    _write_package(pkg_dir, name="haybale-alpha", version="0.0.3")

    entry = generate_marketstall.build_entry(pkg_dir, source="git")

    assert entry["source"] == "git"
    install_spec = cast(str, entry["install_spec"])
    assert install_spec.startswith("haybale-alpha @ git+")
    assert "#subdirectory=" in install_spec


@pytest.mark.unit
def test_build_entry_falls_back_to_pyproject_when_haybale_toml_absent(tmp_path: Path) -> None:
    """A package with no haybale.toml still produces a row (name/version from
    pyproject; label falls back to the dist name via the shared builder)."""
    pkg_dir = tmp_path / "haybale-bare"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "haybale-bare"\n'
        'version = "0.0.1"\n'
        'description = "Bare-bones package without a haybale.toml."\n'
        "dependencies = []\n"
    )
    module_dir = pkg_dir / "haybale_bare"
    module_dir.mkdir()
    (module_dir / "__init__.py").write_text('"""no haybale.toml."""\n')

    entry = generate_marketstall.build_entry(pkg_dir)

    assert entry["name"] == "haybale-bare"
    assert entry["version"] == "0.0.1"
    assert entry["label"] == "Bare"  # builder's dist-name-derived fallback
    assert entry["source"] == "pypi"
    assert entry["install_spec"] == "haybale-bare"


@pytest.mark.unit
def test_build_entry_raises_when_pyproject_missing(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "no-pyproject"
    pkg_dir.mkdir()

    with pytest.raises(ValueError, match="no-pyproject"):
        generate_marketstall.build_entry(pkg_dir)


@pytest.mark.unit
def test_emit_stall_toml_round_trips_via_tomllib() -> None:
    entry = {
        "name": "haybale-alpha",
        "id": "alpha",
        "label": "Alpha",
        "version": "0.0.3",
        "description": "alpha desc",
        "source": "pypi",
        "install_spec": "haybale-alpha",
        "tags": ["a", "b"],
        "linked_libraries": ["haybale_beta"],
        "origin": "https://github.com/example/fake-workspace",
        "authors": [{"name": "Alpha Author"}],
    }

    out_text = generate_marketstall.emit_stall_toml(cast(dict, entry))
    import tomllib

    parsed = tomllib.loads(out_text)

    # Per spec §11.3 every stall has exactly one [[haybales]] entry, under the
    # new vocabulary (not legacy [[packages]]).
    assert "packages" not in parsed
    assert len(parsed["haybales"]) == 1
    assert parsed["haybales"][0]["name"] == "haybale-alpha"
    assert parsed["haybales"][0]["linked_libraries"] == ["haybale_beta"]
    assert parsed["haybales"][0]["authors"] == [{"name": "Alpha Author"}]


@pytest.mark.unit
def test_emit_stall_toml_includes_name_in_header() -> None:
    """Each generated stall file's comment header should mention the dist name
    so a human reader can identify it without parsing TOML."""
    entry = {
        "name": "haybale-x",
        "version": "0.0.1",
        "label": "X",
        "description": "d",
        "source": "pypi",
        "install_spec": "haybale-x",
        "tags": [],
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
        "source": "pypi",
        "install_spec": "haybale-x",
        "tags": [],
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
        "source": "pypi",
        "install_spec": "haybale-multi",
        "tags": [],
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

    _write_package(tmp_path / "subdir-a/haybale-alpha", name="haybale-alpha", version="0.0.3")
    _write_package(tmp_path / "subdir-a/haybale-beta", name="haybale-beta", version="0.0.3")

    # haybale-internal is in lockstep_unpublished — must NOT appear in output.
    _write_package(tmp_path / "subdir-b/haybale-internal", name="haybale-internal", version="0.0.3")

    result = generate_marketstall.generate(root, feed_base_url="https://feed.example/haywire")

    import tomllib

    # Stalls: one per publish_order entry, in publish order.
    assert [dist for dist, _body in result.stalls] == ["haybale-alpha", "haybale-beta"]
    alpha_parsed = tomllib.loads(result.stalls[0][1])
    assert alpha_parsed["haybales"][0]["name"] == "haybale-alpha"
    assert alpha_parsed["haybales"][0]["version"] == "0.0.3"
    assert alpha_parsed["haybales"][0]["label"] == "Haybale-Alpha"

    # Aggregator: one [[stalls]] per dist, URLs composed under feed_base_url.
    mp_parsed = tomllib.loads(result.marketplace_toml)
    assert [s["url"] for s in mp_parsed["stalls"]] == [
        "https://feed.example/haywire/stalls/haybale-alpha.toml",
        "https://feed.example/haywire/stalls/haybale-beta.toml",
    ]


@pytest.mark.unit
def test_generate_finds_module_dir_regardless_of_entry_point_name(tmp_path: Path) -> None:
    """The module dir is found by `find_module_dir` (flat/src layout scan),
    not by reading [project.entry-points."haywire.libraries"] — so a module
    directory whose name differs from the dist name is still found."""
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        '[tool.haywire.release]\npip_publish_order = ["haybale-foo"]\n'
        "git_publish_order = []\nlockstep_unpublished = []\n"
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/fake-workspace"\n'
        'docs_branch = "main"\n'
        'marketplace = ["haybale-foo"]\n'
    )
    _write_package(
        tmp_path / "pkgs/haybale-foo",
        name="haybale-foo",
        module_name="haybale_foo_renamed",
    )

    import tomllib

    result = generate_marketstall.generate(root, feed_base_url="https://feed.example/x")
    stall_parsed = tomllib.loads(result.stalls[0][1])
    assert stall_parsed["haybales"][0]["name"] == "haybale-foo"


@pytest.mark.unit
def test_generate_tolerates_missing_haybale_toml(tmp_path: Path) -> None:
    """A package with no haybale.toml still generates an entry, falling back
    to pyproject name/version/description via the shared builder."""
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        '[tool.haywire.release]\npip_publish_order = ["haybale-ghost"]\n'
        "git_publish_order = []\nlockstep_unpublished = []\n"
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        'marketplace = ["haybale-ghost"]\n'
    )
    pkg = tmp_path / "pkgs/haybale-ghost"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "haybale-ghost"\nversion = "0.0.1"\ndescription = "no init"\ndependencies = []\n'
    )
    module_dir = pkg / "haybale_ghost"
    module_dir.mkdir()
    (module_dir / "__init__.py").write_text('"""no haybale.toml."""\n')

    import tomllib

    result = generate_marketstall.generate(root, feed_base_url="https://feed.example/x")
    stall_parsed = tomllib.loads(result.stalls[0][1])
    entry = stall_parsed["haybales"][0]
    assert entry["name"] == "haybale-ghost"
    assert entry["label"] == "Ghost"  # builder's dist-name-derived fallback


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

    _write_package(tmp_path / "subdir-a/haybale-alpha", name="haybale-alpha", version="0.0.3")
    _write_package(tmp_path / "subdir-a/haybale-beta", name="haybale-beta", version="0.0.3")

    # lockstep_unpublished entry must exist on disk per locate_packages, even
    # though it won't appear in the generated output (publish_order only).
    _write_package(tmp_path / "subdir-b/haybale-internal", name="haybale-internal", version="0.0.3")

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
def test_generate_accepts_relative_root_pyproject_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--root` (default ./pyproject.toml) is relative when generate_marketstall.py
    is invoked the way CI invokes it: `python scripts/generate_marketstall.py`
    from the repo root. `_build_entry_for_library` walks up from the package
    directory to find the git root via `.resolve()`, so a relative `pkg_dir`
    passed alongside it raises ValueError on `.relative_to()` — this is the
    real repo checkout (which has a git root and remote), run with a relative
    root path, guarding against that regression."""
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)

    result = generate_marketstall.generate(Path("pyproject.toml"))

    assert result.stalls


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
        'marketplace = ["haybale-alpha", "haybale-unknown"]\n'
    )
    _write_package(tmp_path / "pkgs/haybale-alpha", name="haybale-alpha")

    with pytest.raises(ValueError, match="haybale-unknown"):
        generate_marketstall.generate(root, feed_base_url="https://feed.example/x")


@pytest.mark.unit
def test_generated_rows_parse_back_through_the_real_parser() -> None:
    """The feed must be readable by the parser consumers actually use.

    The script drifted for months because its tests asserted its own output
    shape rather than round-tripping it through _parse_haybale_entry.
    """
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    repo_root = Path(__file__).resolve().parents[2]

    result = generate_marketstall.generate(repo_root / "pyproject.toml")

    import tomllib

    rows_by_name: dict[str, dict] = {}
    for dist_name, stall_body in result.stalls:
        parsed = tomllib.loads(stall_body)
        haybales = parsed["haybales"]
        assert len(haybales) == 1
        raw_row = haybales[0]
        assert raw_row["name"] == dist_name
        # The removed/renamed decorator-era keys must never appear on a
        # generated row.
        assert "author" not in raw_row
        assert "dependencies" not in raw_row
        assert "source_url" not in raw_row
        assert "docs_url" not in raw_row
        rows_by_name[dist_name] = _parse_haybale_entry(raw_row).__dict__

    core = rows_by_name["haybale-core"]
    # Read haybale-core's own declared haybale.toml so the assertions below
    # verify against its actual authored values, not invented expectations.
    declared = tomllib.loads((repo_root / "barn/haybale-core/haybale_core/haybale.toml").read_text())

    assert core["label"] == declared["label"] == "Core"
    assert core["id"] == declared["id"] == "core"
    assert core["origin"]
    assert core["authors"], "authors must be non-empty"
    for entry in core["authors"]:
        assert isinstance(entry, tuple)
        assert len(entry) == 2
        name, url = entry
        assert isinstance(name, str)
        assert name
        assert isinstance(url, str)
    assert core["tags"], "tags must be non-empty"


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
        'marketplace = ["haybale-alpha"]\n'
    )
    _write_package(tmp_path / "pkgs/haybale-alpha", name="haybale-alpha")

    with pytest.raises(ValueError, match="haybale-alpha"):
        generate_marketstall.generate(root, feed_base_url="https://feed.example/x")

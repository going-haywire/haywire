"""Tests for LibraryManager.dry_run() and _parse_dry_run_removals()."""

from __future__ import annotations

from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_manager():
    from haybale_marketplace.library_manager import LibraryManager

    registry = MagicMock()
    registry._library_distribution_names = {}
    registry._library_install_types = {}
    registry._library_sources = {}
    return LibraryManager(library_registry=registry)


@pytest.mark.unit
def test_parse_dry_run_removals_extracts_minus_lines():
    """_parse_dry_run_removals must return normalised dist names from ' - name==ver' lines."""
    mgr = _make_manager()
    output = (
        "Resolved 68 packages in 912ms\n"
        "Would uninstall 2 packages\n"
        " - haybale-core==0.0.5\n"
        " + haybale-core==0.0.6\n"
        " - haybale-visiongraph==0.0.5\n"
        " + haybale-visiongraph==0.0.6\n"
    )
    result = mgr._parse_dry_run_removals(output)
    assert result == ["haybale-core", "haybale-visiongraph"]


@pytest.mark.unit
def test_parse_dry_run_removals_no_changes():
    """_parse_dry_run_removals must return empty list for 'Would make no changes'."""
    mgr = _make_manager()
    output = "Resolved 12 packages in 120ms\nWould make no changes\n"
    result = mgr._parse_dry_run_removals(output)
    assert result == []


@pytest.mark.unit
def test_parse_dry_run_removals_empty_output():
    """_parse_dry_run_removals must return empty list for empty output."""
    mgr = _make_manager()
    assert mgr._parse_dry_run_removals("") == []


@pytest.mark.unit
async def test_dry_run_returns_removals_list():
    """dry_run() must call uv with --dry-run and return parsed removal names."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        # Simulate uv output for a dry-run that would upgrade haybale-core
        on_output(" - haybale-core==0.0.5")
        on_output(" + haybale-core==0.0.6")
        return True, ""

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        result = await mgr.dry_run("haybale-visiongraph")

    assert result == ["haybale-core"]


@pytest.mark.unit
async def test_dry_run_already_satisfied_returns_empty():
    """dry_run() must return [] when uv reports no changes needed."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        on_output("Would make no changes")
        return True, ""

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        result = await mgr.dry_run("haybale-visiongraph==0.0.6")

    assert result == []


@pytest.mark.unit
async def test_dry_run_remote_spec_uses_no_sources():
    """Regression: remote specs must pass --no-sources so [tool.uv.sources] inside a
    cloned git tree (e.g. workspace dev path overrides) does not corrupt resolution.

    A published haybale's git+URL may clone into a workspace whose root pyproject
    has hardcoded local paths in [tool.uv.sources]; uv applies them and replaces
    already-installed editable packages with bogus path-traversal git URLs.
    """
    mgr = _make_manager()
    captured: dict[str, list[str]] = {}

    async def fake_run(args, on_output):
        captured["args"] = list(args)
        return True, ""

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        await mgr.dry_run("haybale-visiongraph @ git+https://example.com/foo.git")

    assert "--no-sources" in captured["args"]
    assert "--dry-run" in captured["args"]


@pytest.mark.unit
async def test_dry_run_local_dir_omits_no_sources(tmp_path):
    """Editable installs of a local directory must NOT pass --no-sources.

    Local-dir installs are for project heaps which legitimately use
    [tool.uv.sources] to point at the haywire dev repo.
    """
    mgr = _make_manager()
    captured: dict[str, list[str]] = {}

    async def fake_run(args, on_output):
        captured["args"] = list(args)
        return True, ""

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        await mgr.dry_run(str(tmp_path))

    assert "--no-sources" not in captured["args"]
    assert "-e" in captured["args"]


@pytest.mark.unit
async def test_dry_run_resolver_error_raises():
    """dry_run() must raise RuntimeError when uv exits non-zero."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        return False, "error: no solution found"

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="no solution found"):
            await mgr.dry_run("haybale-bad-pkg")


@pytest.mark.unit
def test_framework_constraints_pins_installed_versions():
    """The constraint set is exactly core/studio/nicegui, pinned == to what is
    installed — never to a declared Requires-Dist, which can itself be stale."""
    from haybale_marketplace.library_manager import FRAMEWORK_PACKAGES

    mgr = _make_manager()

    def fake_version(name: str) -> str:
        return {"haywire-core": "0.0.34", "haywire-studio": "0.0.34", "nicegui": "3.13.0"}[name]

    with patch("importlib.metadata.version", side_effect=fake_version):
        lines = mgr._framework_constraints()

    assert lines == ["haywire-core==0.0.34", "haywire-studio==0.0.34", "nicegui==3.13.0"]
    assert FRAMEWORK_PACKAGES == ("haywire-core", "haywire-studio", "nicegui")


@pytest.mark.unit
def test_framework_constraints_skips_missing_packages():
    """A package that isn't installed contributes no constraint — pinning a
    version we don't have would make every install unsatisfiable."""
    import importlib.metadata as _meta

    mgr = _make_manager()

    def fake_version(name: str) -> str:
        if name == "nicegui":
            raise _meta.PackageNotFoundError(name)
        return "0.0.34"

    with patch("importlib.metadata.version", side_effect=fake_version):
        lines = mgr._framework_constraints()

    assert lines == ["haywire-core==0.0.34", "haywire-studio==0.0.34"]


@pytest.mark.unit
async def test_dry_run_passes_constraints_file():
    """dry_run() must pass -c <file> so a haybale that needs a different core
    version fails at the resolver instead of silently moving the framework."""
    mgr = _make_manager()
    captured: dict[str, list[str]] = {}

    async def fake_run(args, on_output):
        captured["args"] = list(args)
        idx = args.index("-c")
        captured["body"] = Path(args[idx + 1]).read_text()
        return True, ""

    with patch.object(mgr, "_framework_constraints", return_value=["haywire-core==0.0.34"]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            await mgr.dry_run("haybale-foo")

    assert "-c" in captured["args"]
    assert captured["body"] == "haywire-core==0.0.34\n"


@pytest.mark.unit
async def test_install_passes_identical_flags_to_dry_run():
    """install() and dry_run() must agree on every resolver-affecting flag, or
    the pre-eviction set and the actual install diverge."""
    mgr = _make_manager()
    seen: list[list[str]] = []

    async def fake_run(args, on_output):
        seen.append(list(args))
        return True, ""

    mgr.registry.list_names.return_value = []
    with patch.object(mgr, "_framework_constraints", return_value=["haywire-core==0.0.34"]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            await mgr.install("haybale-foo", lambda line: None)

    dry_flags = [a for a in seen[0] if a.startswith("-") and a != "-c"]
    install_flags = [a for a in seen[1] if a.startswith("-") and a != "-c"]
    assert dry_flags == ["--dry-run", "--no-sources"]
    assert install_flags == ["--no-sources"]
    assert "-c" in seen[0] and "-c" in seen[1]


@pytest.mark.unit
async def test_dry_run_resolver_failure_names_the_shell_control():
    """A framework-blocked install must tell the user where the remedy lives —
    the shell's check-for-updates control — not dump raw resolver text alone."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        return False, "error: no solution found: haywire-core==0.0.34 is unsatisfiable"

    with patch.object(mgr, "_framework_constraints", return_value=["haywire-core==0.0.34"]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            with pytest.raises(RuntimeError) as exc:
                await mgr.dry_run("haybale-foo")

    assert "Check for updates" in str(exc.value)
    assert "no solution found" in str(exc.value)

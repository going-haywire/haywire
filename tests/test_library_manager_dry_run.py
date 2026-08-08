"""Tests for LibraryManager.dry_run() and _parse_dry_run_removals()."""

from __future__ import annotations

import threading
from pathlib import Path

from typing import Any, cast

import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_manager():
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.library.identity import LibraryIdentity

    registry = MagicMock()
    registry._library_distribution_names = {}
    registry._library_install_types = {}
    registry._library_sources = {}
    # A real identity, not a MagicMock attribute: the manager reads the typed
    # `on_reload` off it and orders it against other libraries' declarations,
    # which a Mock cannot participate in.
    registry.get_library_identity.side_effect = lambda lid: LibraryIdentity(
        label=lid,
        version="0.0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path=f"/tmp/{lid}",
        module_name=lid,
        id=lid,
    )
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
        captured["body"] = cast(Any, Path(args[idx + 1]).read_text())
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
    assert dry_flags == ["--dry-run", "--no-sources", "--refresh-package"]
    assert install_flags == ["--no-sources", "--refresh-package"]
    assert "-c" in seen[0]
    assert "-c" in seen[1]
    # The refreshed package must be the one being installed, in both calls.
    assert seen[0][seen[0].index("--refresh-package") + 1] == "haybale-foo"
    assert seen[1][seen[1].index("--refresh-package") + 1] == "haybale-foo"


@pytest.mark.unit
async def test_dry_run_resolver_failure_names_the_shell_control():
    """A framework-blocked install must tell the user where the remedy lives —
    the shell's check-for-updates control — not dump raw resolver text alone.

    "Framework-blocked" is proven, not assumed: the constrained resolve fails
    and the unconstrained one succeeds, so the constraints file (which pins the
    framework to what is installed) is what blocked it.
    """
    mgr = _make_manager()

    async def fake_run(args, on_output):
        if "-c" in args:
            return False, "error: no solution found: haywire-core==0.0.34 is unsatisfiable"
        return True, ""  # drops the constraints -> resolves fine

    with patch.object(mgr, "_framework_constraints", return_value=["haywire-core==0.0.34"]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            with pytest.raises(RuntimeError) as exc:
                await mgr.dry_run("haybale-foo")

    assert "Check for updates" in str(exc.value)
    assert "no solution found" in str(exc.value)
    # The versions actually running — the half uv's output cannot supply.
    assert "haywire-core 0.0.34" in str(exc.value)


@pytest.mark.unit
async def test_dry_run_unproven_failure_does_not_blame_the_framework():
    """When dropping the constraints does NOT fix the resolve, the framework is
    not the proven cause and must not be named.

    The regression this locks down: a stale uv index cache hides a published
    version, uv says "no version of X", and the old code told the user to
    upgrade Haywire — advice that cannot fix a cache and sends them to a
    control that will report no update available.
    """
    mgr = _make_manager()

    async def fake_run(args, on_output):
        return False, "no version of haybale-foo==0.0.37"  # fails with AND without -c

    with patch.object(mgr, "_framework_constraints", return_value=["haywire-core==0.0.34"]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            with pytest.raises(RuntimeError) as exc:
                await mgr.dry_run("haybale-foo==0.0.37")

    assert "Check for updates" not in str(exc.value)
    assert "Haywire framework" not in str(exc.value)
    assert "no version of haybale-foo==0.0.37" in str(exc.value)


@pytest.mark.unit
async def test_dry_run_refreshes_the_index_for_the_target_package():
    """uv does not revalidate a cached index page on a resolution miss, so a
    just-published version reads as nonexistent until the TTL expires. The
    install path must refresh the one package it is acting on."""
    mgr = _make_manager()
    captured: dict[str, list[str]] = {}

    async def fake_run(args, on_output):
        captured["args"] = list(args)
        return True, ""

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        await mgr.dry_run("haybale-marketplace==0.0.37")

    args = captured["args"]
    assert args[args.index("--refresh-package") + 1] == "haybale-marketplace"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("haybale-foo", "haybale-foo"),
        ("haybale-foo==0.0.37", "haybale-foo"),
        ("haybale-foo>=1.0,<2", "haybale-foo"),
        ("haybale-foo[extra]==1.0", "haybale-foo"),
        ("haybale-foo @ git+https://example.com/x.git", "haybale-foo"),
        ("git+https://example.com/x.git", None),
    ],
)
def test_spec_package_name_covers_every_spec_shape(spec, expected):
    """--refresh-package needs a distribution name; a bare git+URL has none."""
    from haybale_marketplace.library_manager import LibraryManager

    assert LibraryManager._spec_package_name(spec) == expected


@pytest.mark.unit
async def test_install_with_known_removals_skips_the_second_resolve():
    """A caller that already ran dry_run() must not pay for a second one.

    The UI flow shows the user the collateral upgrades from its own dry_run
    and then confirms; recomputing them inside install() would both cost a
    second resolver round and risk acting on a different set than the one
    approved.
    """
    mgr = _make_manager()
    seen: list[list[str]] = []

    async def fake_run(args, on_output):
        seen.append(list(args))
        return True, ""

    mgr.registry.list_names.return_value = []
    with patch.object(mgr, "_framework_constraints", return_value=[]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            await mgr.install("haybale-foo", lambda line: None, None, [])

    # Exactly one uv invocation: the install itself, no --dry-run pass.
    assert len(seen) == 1
    assert "--dry-run" not in seen[0]


@pytest.mark.unit
async def test_install_without_known_removals_still_dry_runs():
    """The default path is unchanged for every non-UI caller."""
    mgr = _make_manager()
    seen: list[list[str]] = []

    async def fake_run(args, on_output):
        seen.append(list(args))
        return True, ""

    mgr.registry.list_names.return_value = []
    with patch.object(mgr, "_framework_constraints", return_value=[]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            await mgr.install("haybale-foo", lambda line: None)

    assert len(seen) == 2
    assert "--dry-run" in seen[0]


@pytest.mark.unit
async def test_known_removals_drives_the_eviction_set():
    """The supplied list is what gets evicted — not a recomputed one."""
    from haywire.core.library.install_type import InstallType

    mgr = _make_manager()

    async def fake_run(args, on_output):
        return True, ""

    mgr.registry.list_names.return_value = []
    mgr.registry.find_library_by_distribution_name.return_value = "vision"
    mgr.registry.get_library_install_type.return_value = InstallType.REGULAR

    with patch.object(mgr, "_framework_constraints", return_value=[]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            with patch.object(mgr, "dry_run") as never_called:
                await mgr.install("haybale-foo", lambda line: None, None, ["haybale-vision"])

    never_called.assert_not_called()
    mgr.registry.remove_library.assert_called_once_with("vision")


@pytest.mark.unit
async def test_empty_known_removals_is_not_treated_as_absent():
    """[] means 'nothing to evict', not 'go find out' — the distinction is None."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        return True, ""

    mgr.registry.list_names.return_value = []
    with patch.object(mgr, "_framework_constraints", return_value=[]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            with patch.object(mgr, "dry_run") as never_called:
                await mgr.install("haybale-foo", lambda line: None, None, [])

    never_called.assert_not_called()
    mgr.registry.remove_library.assert_not_called()


@pytest.mark.unit
async def test_streaming_emits_carriage_return_progress_updates():
    """uv renders download progress with \\r and no newline.

    A line-oriented reader emits nothing until the bar finishes — for a large
    package that is 30+ seconds of a log that looks hung. Each \\r-terminated
    frame must surface as it arrives.
    """
    import sys

    mgr = _make_manager()
    script = (
        "import sys\n"
        "for pct in (0, 50, 100):\n"
        "    sys.stdout.write(f'Downloading {pct}%\\r'); sys.stdout.flush()\n"
        "sys.stdout.write('Installed 1 package\\n')\n"
    )
    seen: list[str] = []
    with patch.object(mgr, "_uv_cmd", return_value=[sys.executable, "-c", script]):
        ok, tail = await mgr._run_uv_streaming(["ignored"], seen.append)

    assert ok
    assert seen == [
        "Downloading 0%",
        "Downloading 50%",
        "Downloading 100%",
        "Installed 1 package",
    ]


@pytest.mark.unit
async def test_streaming_emits_trailing_output_without_newline():
    """A final line with no trailing newline must not be swallowed."""
    import sys

    mgr = _make_manager()
    script = "import sys; sys.stdout.write('no trailing newline')"
    seen: list[str] = []
    with patch.object(mgr, "_uv_cmd", return_value=[sys.executable, "-c", script]):
        await mgr._run_uv_streaming(["ignored"], seen.append)

    assert seen == ["no trailing newline"]


@pytest.mark.unit
async def test_streaming_normalizes_crlf_to_one_break():
    """CRLF is one line ending, not an empty line between two."""
    import sys

    mgr = _make_manager()
    script = "import sys; sys.stdout.write('alpha\\r\\nbeta\\r\\n')"
    seen: list[str] = []
    with patch.object(mgr, "_uv_cmd", return_value=[sys.executable, "-c", script]):
        await mgr._run_uv_streaming(["ignored"], seen.append)

    assert seen == ["alpha", "beta"]


@pytest.mark.unit
async def test_streaming_reports_failure_with_recent_lines():
    """The error tail must survive the chunked reader."""
    import sys

    mgr = _make_manager()
    script = "import sys; sys.stdout.write('boom\\n'); sys.exit(1)"
    seen: list[str] = []
    with patch.object(mgr, "_uv_cmd", return_value=[sys.executable, "-c", script]):
        ok, tail = await mgr._run_uv_streaming(["ignored"], seen.append)

    assert ok is False
    assert "boom" in tail


@pytest.mark.unit
async def test_install_enables_libraries_off_the_event_loop():
    """Enabling imports every library's module tree — seconds for a package
    like haybale-visiongraph. On the event loop that stops NiceGUI answering
    its heartbeat and the browser reports the connection lost mid-install.
    """
    import asyncio as _asyncio

    mgr = _make_manager()
    called_in_thread: dict[str, bool] = {}
    main_thread = threading.current_thread()

    def _enable_all():
        called_in_thread["off_loop"] = threading.current_thread() is not main_thread

    mgr.registry.list_names.return_value = []
    mgr.registry.enable_all_libraries.side_effect = _enable_all

    async def fake_run(args, on_output):
        return True, ""

    with patch.object(mgr, "_framework_constraints", return_value=[]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            with patch.object(_asyncio, "to_thread", wraps=_asyncio.to_thread) as spy:
                await mgr.install("haybale-foo", lambda line: None, None, [])

    assert called_in_thread.get("off_loop") is True
    threaded = {c.args[0] for c in spy.call_args_list if c.args}
    assert mgr.registry.enable_all_libraries in threaded
    assert mgr.registry.scan_for_libraries in threaded

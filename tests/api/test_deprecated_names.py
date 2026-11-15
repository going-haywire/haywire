"""A deprecated Author API name: served with a notice, recorded for the library (ADR 0085)."""

from __future__ import annotations

import importlib
import sys
import textwrap

import pytest

import haywire.api as component
from haywire.core.errors import ErrorSeverity
from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.library.deprecated_names import (
    DeprecatedName,
    HaywireDeprecationWarning,
    recorded_deprecations,
)
from haywire.core.registry.folder_scan import FolderScanMixin

pytestmark = pytest.mark.unit


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=5)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


@pytest.fixture
def old_name(monkeypatch):
    """``haywire.api.OldNode`` deprecated in favour of ``BaseNode``."""
    entry = DeprecatedName("haywire.core.node:BaseNode", "haywire.api.BaseNode", "9.9.0")
    monkeypatch.setitem(component._DEPRECATED, "OldNode", entry)


@pytest.fixture
def library_module(tmp_path, monkeypatch):
    """An importable module that imports the deprecated name."""
    (tmp_path / "lib_using_old_name.py").write_text(
        textwrap.dedent(
            """
            from haywire.api import OldNode


            class Mine(OldNode):
                pass
            """
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    yield "lib_using_old_name"
    sys.modules.pop("lib_using_old_name", None)


def test_a_deprecated_name_resolves_and_warns(old_name) -> None:
    with pytest.warns(HaywireDeprecationWarning, match=r"removed in 9\.9\.0.*Use haywire\.api\.BaseNode"):
        assert component.OldNode is component.BaseNode


def test_an_unknown_name_is_an_attribute_error() -> None:
    with pytest.raises(AttributeError):
        _ = component.NoSuchName


def test_outside_a_library_import_nothing_is_recorded(old_name, ledger) -> None:
    with pytest.warns(HaywireDeprecationWarning):
        _ = component.OldNode
    assert ledger.query().total == 0


@pytest.mark.filterwarnings("ignore::haywire.core.library.deprecated_names.HaywireDeprecationWarning")
def test_the_import_of_a_library_module_records_one_warning(old_name, library_module, ledger) -> None:
    with recorded_deprecations(library_module):
        importlib.import_module(library_module)
    entries = ledger.query().entries
    assert len(entries) == 1
    assert entries[0].severity is ErrorSeverity.WARNING
    assert entries[0].module_name == library_module
    assert "haywire.api.OldNode is deprecated" in entries[0].message


@pytest.mark.filterwarnings("ignore::haywire.core.library.deprecated_names.HaywireDeprecationWarning")
def test_a_reload_records_it_again(old_name, library_module, ledger) -> None:
    """The folder scan re-executes the module on hot reload, so the notice returns."""
    scan = FolderScanMixin()
    for _ in range(2):
        scan.module_scan_for_classes(library_module, None, lambda cls: False, force_reload=True)
    # The ledger folds a repeat of an unread entry into it and counts it.
    assert [entry.count for entry in ledger.query().entries] == [2]


@pytest.mark.filterwarnings("ignore::haywire.core.library.deprecated_names.HaywireDeprecationWarning")
def test_a_failing_import_still_records_the_notice(old_name, tmp_path, monkeypatch, ledger) -> None:
    (tmp_path / "lib_that_breaks.py").write_text("from haywire.api import OldNode\nraise RuntimeError\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(RuntimeError), recorded_deprecations("lib_that_breaks"):
        importlib.import_module("lib_that_breaks")
    assert ledger.query().total == 1

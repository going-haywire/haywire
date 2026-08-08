"""The single reader for @library(...) source.

AST, not regex: the regex readers this replaces could be defeated by quoting
(the foundation plan shipped a fix for exactly that bug), and one of them
converted `_` to `-` on every list value because it was written for dependency
names.
"""

from pathlib import Path

import pytest

from haywire.core.publishing.manifest.decorator_ast import DecoratorFields, read_decorator

FULL = """from haywire.core.library.decorator import library


@library(
    id="core",
    label="Core",
    linked_libraries=["haybale_studio", "haybale_graph_editor"],
    on_reload="restart",
    os=["macos", "linux"],
    examples_path="examples/OVERVIEW.md",
    tests_path="tests/",
    file_watcher=True,
)
class Library:
    pass
"""

MINIMAL = """from haywire.core.library.decorator import library


@library(id="min", label="Min")
class Library:
    pass
"""


def _write(tmp_path: Path, source: str) -> Path:
    init_py = tmp_path / "__init__.py"
    init_py.write_text(source)
    return init_py


def test_reads_every_field(tmp_path):
    got = read_decorator(_write(tmp_path, FULL))
    assert got == DecoratorFields(
        id="core",
        label="Core",
        linked_libraries=["haybale_studio", "haybale_graph_editor"],
        on_reload="restart",
        os=["macos", "linux"],
        examples_path="examples/OVERVIEW.md",
        tests_path="tests/",
        file_watcher=True,
    )


def test_unauthored_fields_take_defaults(tmp_path):
    got = read_decorator(_write(tmp_path, MINIMAL))
    assert got.id == "min"
    assert got.label == "Min"
    assert got.linked_libraries == []
    assert got.on_reload == "none"
    assert got.os == []
    assert got.examples_path == ""
    assert got.file_watcher is False


def test_module_names_are_not_converted_to_pip_names(tmp_path):
    """The regex reader this replaces did `_` -> `-`; module names are authoritative."""
    got = read_decorator(_write(tmp_path, FULL))
    assert got.linked_libraries == ["haybale_studio", "haybale_graph_editor"]


def test_underscored_values_survive(tmp_path):
    """The old converter silently mangled any value containing an underscore."""
    source = '@library(id="x", label="X", os=["mac_os"])\nclass Library: pass\n'
    assert read_decorator(_write(tmp_path, source)).os == ["mac_os"]


@pytest.mark.parametrize("quote", ["'", '"'])
def test_both_quote_styles(tmp_path, quote):
    source = f"@library(id={quote}q{quote}, label={quote}Q{quote})\nclass Library: pass\n"
    assert read_decorator(_write(tmp_path, source)).label == "Q"


def test_missing_file_yields_defaults(tmp_path):
    assert read_decorator(tmp_path / "nope.py") == DecoratorFields()


def test_file_without_a_decorator_yields_defaults(tmp_path):
    """Framework packages have no Library class; that is not an error."""
    assert read_decorator(_write(tmp_path, "x = 1\n")) == DecoratorFields()


def test_unparseable_file_yields_defaults(tmp_path):
    """A syntax error in a library must not crash a read-only report."""
    assert read_decorator(_write(tmp_path, "def (\n")) == DecoratorFields()


def test_non_literal_values_are_skipped_not_guessed(tmp_path):
    """A computed value cannot be read statically; report absent, never wrong."""
    source = "@library(id=NAME, label=_compute(), linked_libraries=[*OTHERS])\nclass Library: pass\n"
    got = read_decorator(_write(tmp_path, source))
    assert got.id == ""
    assert got.label == ""
    assert got.linked_libraries == []


def test_decorated_class_found_below_other_statements(tmp_path):
    source = "import os\n\nCONST = 1\n\n\n@library(id='deep', label='Deep')\nclass Library: pass\n"
    assert read_decorator(_write(tmp_path, source)).id == "deep"


def test_legacy_dependencies_keyword_is_not_read(tmp_path):
    """`dependencies=` is no longer a decorator field. The reader must not
    resurrect it: a library still writing it will not load at all, so reporting
    its value as a linked library would describe a library that cannot exist."""
    source = '@library(id="x", label="X", dependencies=["haybale_core"])\nclass Library: pass\n'
    assert read_decorator(_write(tmp_path, source)).linked_libraries == []

"""AST imports plus registry-key literals. Prose is reported, never rewritten."""

from __future__ import annotations

import pytest

OLD_DIST, NEW_DIST = "haybale-foo", "hay-bar"
OLD_MOD, NEW_MOD = "haybale_foo", "hay_bar"


def _rw(src: str):
    from haywire_studio.packaging.rename.pysource import rewrite_source

    return rewrite_source(src, OLD_DIST, NEW_DIST, OLD_MOD, NEW_MOD)


@pytest.mark.unit
def test_rewrites_from_import():
    out, n = _rw("from haybale_foo.types.math import MathOPs\n")
    assert out == "from hay_bar.types.math import MathOPs\n"
    assert n == 1


@pytest.mark.unit
def test_rewrites_plain_and_aliased_import():
    assert _rw("import haybale_foo\n")[0] == "import hay_bar\n"
    assert _rw("import haybale_foo as hf\n")[0] == "import hay_bar as hf\n"


@pytest.mark.unit
def test_rewrites_function_local_import_preserving_indent():
    out, n = _rw("def f():\n    from haybale_foo.types import X\n    return X\n")
    assert "    from hay_bar.types import X" in out
    assert n == 1


@pytest.mark.unit
def test_leaves_relative_imports_alone():
    src = "from ._state import Flow\nfrom ..copy import STEPS\n"
    assert _rw(src) == (src, 0)


@pytest.mark.unit
def test_does_not_rewrite_lookalike_module():
    src = "import haybale_foobar\n"
    assert _rw(src) == (src, 0)


@pytest.mark.unit
def test_rewrites_comma_joined_import_only_matching_name():
    out, n = _rw("import haybale_foo, os\n")
    assert out == "import hay_bar, os\n"
    assert n == 1


@pytest.mark.unit
def test_rewrites_semicolon_joined_import_statements():
    out, n = _rw("import haybale_foo; import os\n")
    assert out == "import hay_bar; import os\n"
    assert n == 1


@pytest.mark.unit
def test_does_not_rewrite_lookalike_module_in_comma_joined_import():
    """Regression guard: word-boundary matching must not false-positive on a
    longer identifier sharing the prefix, even alongside other rewritable names."""
    src = "import haybale_foobar, haybale_foo\n"
    out, n = _rw(src)
    assert out == "import haybale_foobar, hay_bar\n"
    assert n == 1


@pytest.mark.unit
def test_rewrites_self_referencing_registry_key_literal():
    """types/specs.py:9 does exactly this — an unrewritten key dangles."""
    src = 'X = spec(widget_key="haybale-foo:widget:TemperatureWidget")\n'
    out, n = _rw(src)

    assert out == 'X = spec(widget_key="hay-bar:widget:TemperatureWidget")\n'
    assert n == 1


@pytest.mark.unit
def test_rewrites_key_literal_in_single_quotes():
    out, _ = _rw("K = 'haybale-foo:node:Add'\n")
    assert out == "K = 'hay-bar:node:Add'\n"


@pytest.mark.unit
def test_does_not_rewrite_other_libraries_keys():
    src = 'W = "haywire-core:widget:NumberWidget"\n'
    assert _rw(src) == (src, 0)


@pytest.mark.unit
def test_does_not_rewrite_prose_mentioning_the_name():
    """A db path literal is wrong after rename, but the data has not moved."""
    src = '"""Creates ~/.haywire/db/haybale_foo/config.toml."""\nN = "haybale-foo is nice"\n'
    assert _rw(src) == (src, 0)


@pytest.mark.unit
def test_counts_both_kinds_together():
    src = 'from haybale_foo.a import B\nK = "haybale-foo:node:Add"\n'
    out, n = _rw(src)

    assert "from hay_bar.a import B" in out
    assert '"hay-bar:node:Add"' in out
    assert n == 2


@pytest.mark.unit
def test_scan_prose_reports_only_unhandled_lines():
    from haywire_studio.packaging.rename.pysource import scan_prose

    src = (
        "import haybale_foo\n"
        'K = "haybale-foo:node:Add"\n'
        'P = "~/.haywire/db/haybale_foo/x"\n'
        "# note: haybale-foo\n"
    )
    assert scan_prose(src, OLD_MOD, OLD_DIST) == [3, 4]


@pytest.mark.unit
def test_preserves_comments_and_blank_lines():
    out, _ = _rw("from haybale_foo import A  # keep me\n\n\nY = 2\n")
    assert out == "from hay_bar import A  # keep me\n\n\nY = 2\n"


@pytest.mark.unit
def test_comma_joined_import_excluded_from_prose_because_actually_rewritten():
    """A line the AST detects as an import must not vanish from both the rewrite
    output AND the prose report — verify it's excluded because it WAS rewritten,
    not merely because the AST proved it's an import."""
    from haywire_studio.packaging.rename.pysource import scan_prose

    src = "import haybale_foo, os\n"
    out, n = _rw(src)
    assert n >= 1
    assert scan_prose(src, OLD_MOD, OLD_DIST) == []

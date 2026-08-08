"""The decorator writer must handle double-quoted decorators — which is all of them.

Regression test: the original implementation used single-quote-only regexes
(`(    label=')[^']*(')`), so every write silently no-opped against
`ruff format` output.

The end-to-end half of this file drove LibraryManager.update_library_identity,
which no longer exists — metadata is written by the Share pipeline's metadata
step now (see tests/share_pipeline/test_metadata_step.py). What remains is the
`decorator_io` rewriter itself, which both paths depend on.
"""

import pytest

from haywire.core.library.decorator_io import _set_decorator_str_field

DOUBLE_QUOTED = """from haywire.core.library.decorator import library


@library(
    label="Old Label",
    id="demo",
    description="Old description",
    url="https://old.example",
    author="Old Author",
    author_url="https://old-author.example",
    file_watcher=True,
)
class Library:
    pass
"""


@pytest.mark.parametrize(
    ("field", "new_value"),
    [
        ("label", "New Label"),
        ("description", "New description"),
        ("url", "https://new.example"),
        ("author", "New Author"),
        ("author_url", "https://new-author.example"),
    ],
)
def test_set_decorator_str_field_rewrites_double_quoted(field, new_value):
    result = _set_decorator_str_field(DOUBLE_QUOTED, field, new_value)
    assert f'{field}="{new_value}"' in result


def test_rewrite_leaves_other_fields_untouched():
    result = _set_decorator_str_field(DOUBLE_QUOTED, "label", "New Label")
    assert 'id="demo"' in result
    assert 'author="Old Author"' in result
    assert "file_watcher=True" in result


def test_rewrite_is_idempotent():
    once = _set_decorator_str_field(DOUBLE_QUOTED, "label", "X")
    twice = _set_decorator_str_field(once, "label", "X")
    assert once == twice

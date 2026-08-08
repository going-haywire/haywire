"""Reading PEP 621 fields back out of installed distribution metadata.

The header shapes here were verified against a real hatchling-built wheel
installed into a clean venv — see the consolidation doc. They are not guesses,
and two of them are easy to get wrong: authors split across Author and
Author-email depending on whether an email was declared, and Keywords arrives
comma-joined rather than as repeated headers.
"""

from email.message import Message

import pytest

from haywire.core.library.distmeta import (
    _clean,
    _parse_authors,
    _parse_keywords,
    _parse_urls,
    distribution_fields,
)


def _md(**headers) -> Message:
    """Build a metadata message; a list value becomes repeated headers."""
    msg = Message()
    for key, value in headers.items():
        name = key.replace("_", "-")
        for item in value if isinstance(value, list) else [value]:
            msg[name] = item
    return msg


def test_author_without_email_is_a_plain_header():
    assert _parse_authors(_md(Author="Haywire Team")) == ["Haywire Team"]


def test_author_with_email_lands_in_author_email():
    md = _md(**{"Author-email": "Jane Doe <jane@example.com>"})
    assert _parse_authors(md) == ["Jane Doe"]


def test_mixed_list_splits_across_both_headers():
    """The case a naive get_all('Author') silently drops."""
    md = _md(
        Author="No Email Person",
        **{"Author-email": "With Email <we@example.com>, bare@example.com"},
    )
    assert _parse_authors(md) == ["No Email Person", "With Email", "bare@example.com"]


def test_email_only_entry_falls_back_to_the_address():
    md = _md(**{"Author-email": "bare@example.com"})
    assert _parse_authors(md) == ["bare@example.com"]


def test_no_author_headers_yields_empty():
    assert _parse_authors(_md(Summary="x")) == []


def test_urls_parse_label_and_target():
    md = _md(
        **{
            "Project-URL": [
                "Homepage, https://example.com/home",
                "Author, https://example.com/author",
                "Custom Label, https://example.com/custom",
            ]
        }
    )
    assert _parse_urls(md) == {
        "Homepage": "https://example.com/home",
        "Author": "https://example.com/author",
        "Custom Label": "https://example.com/custom",
    }


def test_urls_absent_yields_empty():
    assert _parse_urls(_md(Summary="x")) == {}


def test_malformed_url_entry_is_skipped_not_raised():
    md = _md(**{"Project-URL": ["no-comma-here", "Homepage, https://ok"]})
    assert _parse_urls(md) == {"Homepage": "https://ok"}


def test_keywords_split_on_commas():
    assert _parse_keywords(_md(Keywords="alpha,beta,gamma")) == ["alpha", "beta", "gamma"]


def test_keywords_tolerate_spaces_and_blanks():
    assert _parse_keywords(_md(Keywords="alpha, ,beta ")) == ["alpha", "beta"]


def test_keywords_absent_yields_empty():
    assert _parse_keywords(_md(Summary="x")) == []


@pytest.mark.parametrize("value", ["", "UNKNOWN"])
def test_placeholder_summary_is_not_a_description(value):
    """setuptools writes UNKNOWN for an absent field; it is not a description."""
    assert _clean(value) == ""


def test_reads_a_really_installed_distribution():
    """End-to-end against haybale-core, which is installed in this workspace."""
    fields = distribution_fields("haybale-core")
    assert fields["version"]
    assert fields["description"]
    assert isinstance(fields.get("tags", []), list)


def test_absent_distribution_yields_empty_dict():
    assert distribution_fields("haybale-does-not-exist") == {}

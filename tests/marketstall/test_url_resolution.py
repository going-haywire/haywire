"""URL resolution for Add Source — spec §4.2, §4.3."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_classify_blob_url_github() -> None:
    """Blob URLs are normalized to raw before persisting so refresh can fetch them directly."""
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    raw = "https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml"
    result = classify_input("https://github.com/alice/cool-libs/blob/main/marketstall.toml")
    assert result.form is InputForm.BLOB_URL
    assert result.fetch_url == raw
    assert result.persist_url == raw


@pytest.mark.unit
def test_classify_raw_url_github() -> None:
    """Raw URLs round-trip unchanged — they are already fetchable."""
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    url = "https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml"
    result = classify_input(url)
    assert result.form is InputForm.RAW_URL
    assert result.fetch_url == url
    assert result.persist_url == url


@pytest.mark.unit
def test_classify_raw_url_github_with_refs_heads() -> None:
    """The extended ref form `refs/heads/<branch>` is a valid raw URL and must persist unchanged.

    Regression: previously the refresh pipeline rewrote this through blob form,
    which is only valid for short refs, and ended up fetching an HTML page.
    """
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    url = (
        "https://raw.githubusercontent.com/going-haywire/haybale-visiongraph/"
        "refs/heads/master/marketstall.toml"
    )
    result = classify_input(url)
    assert result.form is InputForm.RAW_URL
    assert result.fetch_url == url
    assert result.persist_url == url


@pytest.mark.unit
def test_classify_blob_url_gitlab() -> None:
    """Same persist-as-raw rule applies to GitLab: blob URLs would return HTML at fetch time."""
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    raw = "https://gitlab.com/alice/cool-libs/-/raw/main/marketstall.toml"
    result = classify_input("https://gitlab.com/alice/cool-libs/-/blob/main/marketstall.toml")
    assert result.form is InputForm.BLOB_URL
    assert result.fetch_url == raw
    assert result.persist_url == raw


@pytest.mark.unit
def test_classify_raw_url_gitlab() -> None:
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    url = "https://gitlab.com/alice/cool-libs/-/raw/main/marketstall.toml"
    result = classify_input(url)
    assert result.form is InputForm.RAW_URL
    assert result.fetch_url == url
    assert result.persist_url == url


@pytest.mark.unit
def test_classify_plain_toml_url() -> None:
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    url = "https://going-haywire.github.io/haywire/marketplace.toml"
    result = classify_input(url)
    assert result.form is InputForm.PLAIN_TOML_URL
    assert result.fetch_url == url
    assert result.persist_url == url


@pytest.mark.unit
def test_classify_file_url() -> None:
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    url = "file:///Users/me/.haywire/db/haybale-marketplace/stalls/x.toml"
    result = classify_input(url)
    assert result.form is InputForm.PLAIN_TOML_URL
    assert result.fetch_url == url
    assert result.persist_url == url


@pytest.mark.unit
def test_classify_bare_repo_url_rejected_github() -> None:
    """Per §4.2: bare repo URLs are rejected at input time. No network probing."""
    from haywire.core.marketstall.url_resolution import (
        BareRepoUrlRejectedError,
        classify_input,
    )

    with pytest.raises(BareRepoUrlRejectedError) as exc_info:
        classify_input("https://github.com/alice/cool-libs")
    assert "marketstall.toml" in str(exc_info.value)
    assert "README" in str(exc_info.value)


@pytest.mark.unit
def test_classify_bare_repo_url_rejected_with_trailing_slash() -> None:
    from haywire.core.marketstall.url_resolution import (
        BareRepoUrlRejectedError,
        classify_input,
    )

    with pytest.raises(BareRepoUrlRejectedError):
        classify_input("https://github.com/alice/cool-libs/")


@pytest.mark.unit
def test_classify_bare_repo_url_rejected_gitlab() -> None:
    from haywire.core.marketstall.url_resolution import (
        BareRepoUrlRejectedError,
        classify_input,
    )

    with pytest.raises(BareRepoUrlRejectedError):
        classify_input("https://gitlab.com/alice/cool-libs")


@pytest.mark.unit
def test_classify_strips_trailing_dot_git() -> None:
    from haywire.core.marketstall.url_resolution import (
        BareRepoUrlRejectedError,
        classify_input,
    )

    with pytest.raises(BareRepoUrlRejectedError):
        classify_input("https://github.com/alice/cool-libs.git")


@pytest.mark.unit
def test_classify_pasted_toml_block() -> None:
    """Form 4: pasted TOML, not a URL."""
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    block = '[[haybales]]\nname = "haybale-foo"\nmin_version = "0.1.0"\n'
    result = classify_input(block)
    assert result.form is InputForm.PASTED_BLOCK
    assert result.toml_body == block

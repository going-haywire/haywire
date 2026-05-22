"""resolve_and_subscribe — spec §4.3 orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_subscribe_marketstall_blob_url(tmp_path: Path) -> None:
    """A blob URL pointing at a marketstall (haybales only) → [[stalls]] entry."""
    from haywire.core.marketstall import resolve_and_subscribe
    from haywire.core.marketstall.parsing import parse_global_marketplace

    global_path = tmp_path / "marketplace.toml"
    paste_dir = tmp_path / "stalls"

    body = '[[haybales]]\nname = "haybale-foo"\nmin_version = "0.1.0"\n'
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = body.encode()
        result = resolve_and_subscribe(
            global_path,
            "https://github.com/alice/cool-libs/blob/main/marketstall.toml",
            paste_dir=paste_dir,
            cache_dir=tmp_path / "cache",
        )

    assert result.kind == "stall"
    assert result.persist_url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"

    mf = parse_global_marketplace(global_path)
    assert len(mf.stalls) == 1
    assert mf.stalls[0].url == result.persist_url


@pytest.mark.unit
def test_subscribe_marketplace_with_inline_haybales(tmp_path: Path) -> None:
    """A body with [[markets]] (or [[stalls]]) is a marketplace → [[markets]] entry."""
    from haywire.core.marketstall import resolve_and_subscribe
    from haywire.core.marketstall.parsing import parse_global_marketplace

    global_path = tmp_path / "marketplace.toml"

    body = (
        "[[stalls]]\n"
        'url = "https://other.example/marketstall.toml"\n'
        "ignores = []\n"
        "doubles = []\n"
        "blocked = []\n"
        "\n"
        "[[haybales]]\n"
        'name = "haybale-inline"\n'
        'min_version = "0.1.0"\n'
    )
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = body.encode()
        result = resolve_and_subscribe(
            global_path,
            "https://aggregator.example/marketplace.toml",
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )

    assert result.kind == "market"

    mf = parse_global_marketplace(global_path)
    assert len(mf.markets) == 1


@pytest.mark.unit
def test_subscribe_marketplace_with_markets_only(tmp_path: Path) -> None:
    """A body with only [[markets]] (no [[stalls]], no [[haybales]]) is still a marketplace."""
    from haywire.core.marketstall import resolve_and_subscribe
    from haywire.core.marketstall.parsing import parse_global_marketplace

    global_path = tmp_path / "marketplace.toml"

    body = '[[markets]]\nurl = "https://x.example/m.toml"\nignores = []\ndoubles = []\nblocked = []\n'
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = body.encode()
        result = resolve_and_subscribe(
            global_path,
            "https://aggregator.example/marketplace.toml",
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )

    assert result.kind == "market"

    mf = parse_global_marketplace(global_path)
    assert len(mf.markets) == 1


@pytest.mark.unit
def test_subscribe_raw_url_persists_canonical_blob(tmp_path: Path) -> None:
    """A raw URL is fetched as-is but persisted in canonical blob form."""
    from haywire.core.marketstall import resolve_and_subscribe
    from haywire.core.marketstall.parsing import parse_global_marketplace

    global_path = tmp_path / "marketplace.toml"

    body = '[[haybales]]\nname = "haybale-foo"\nmin_version = "0.1.0"\n'
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = body.encode()
        result = resolve_and_subscribe(
            global_path,
            "https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml",
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )

    assert result.persist_url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    mf = parse_global_marketplace(global_path)
    assert mf.stalls[0].url == result.persist_url


@pytest.mark.unit
def test_subscribe_plain_toml_url(tmp_path: Path) -> None:
    """A plain TOML URL is fetched as-is and persisted as-is."""
    from haywire.core.marketstall import resolve_and_subscribe

    global_path = tmp_path / "marketplace.toml"

    body = '[[haybales]]\nname = "haybale-foo"\nmin_version = "0.1.0"\n'
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = body.encode()
        result = resolve_and_subscribe(
            global_path,
            "https://going-haywire.github.io/haywire/marketplace.toml",
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )

    assert result.kind == "stall"
    assert result.persist_url == "https://going-haywire.github.io/haywire/marketplace.toml"


@pytest.mark.unit
def test_subscribe_pasted_toml_block_writes_file(tmp_path: Path) -> None:
    """Pasted TOML block is written to paste_dir/<dist-name>.toml and referenced as file://."""
    from haywire.core.marketstall import resolve_and_subscribe
    from haywire.core.marketstall.parsing import parse_global_marketplace

    global_path = tmp_path / "marketplace.toml"
    paste_dir = tmp_path / "stalls"

    block = '[[haybales]]\nname = "haybale-pasted"\nmin_version = "0.1.0"\n'
    result = resolve_and_subscribe(
        global_path,
        block,
        paste_dir=paste_dir,
        cache_dir=tmp_path / "cache",
    )

    assert result.kind == "stall"
    assert result.persist_url.startswith("file://")
    assert "haybale-pasted.toml" in result.persist_url

    # The file should exist on disk.
    written_file = paste_dir / "haybale-pasted.toml"
    assert written_file.is_file()
    assert "haybale-pasted" in written_file.read_text()

    # The subscription points at the file:// URL.
    mf = parse_global_marketplace(global_path)
    assert mf.stalls[0].url == result.persist_url


@pytest.mark.unit
def test_subscribe_bare_repo_url_rejected(tmp_path: Path) -> None:
    """Bare repo URLs raise BareRepoUrlRejectedError per §4.2."""
    from haywire.core.marketstall import BareRepoUrlRejectedError, resolve_and_subscribe

    with pytest.raises(BareRepoUrlRejectedError):
        resolve_and_subscribe(
            tmp_path / "marketplace.toml",
            "https://github.com/alice/cool-libs",
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )


@pytest.mark.unit
def test_subscribe_pasted_block_with_collapsed_newlines_raises(tmp_path: Path) -> None:
    """A pasted block whose newlines were collapsed (single-line) is malformed TOML.

    Documents the invariant the Add Source dialog must uphold: when a user
    pastes a [[haybales]] block, the input widget must preserve newlines.
    A single-line input that collapses whitespace produces invalid TOML and
    must surface a clear error. The error message must NOT silently succeed.
    """
    from haywire.core.marketstall import SubscribeError, resolve_and_subscribe

    # The exact shape the dialog produces when a single-line input collapses newlines.
    collapsed = '[[haybales]] name = "haybale-test-pasted" min_version = "0.0.1"'
    with pytest.raises(SubscribeError) as exc_info:
        resolve_and_subscribe(
            tmp_path / "marketplace.toml",
            collapsed,
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )
    # The TOML parser's error mentions "Key group not on a line by itself"; the
    # wrapper SubscribeError preserves that message so the user can diagnose.
    assert "malformed" in str(exc_info.value).lower() or "key group" in str(exc_info.value).lower()


@pytest.mark.unit
def test_subscribe_fetch_failure_raises_subscribe_error(tmp_path: Path) -> None:
    """RemoteFetchError → SubscribeError."""
    from haywire.core.marketstall import SubscribeError, resolve_and_subscribe

    with patch("haywire.core.marketstall.cache._urlopen", side_effect=OSError):
        with pytest.raises(SubscribeError) as exc_info:
            resolve_and_subscribe(
                tmp_path / "marketplace.toml",
                "https://gone.example/marketstall.toml",
                paste_dir=tmp_path / "stalls",
                cache_dir=tmp_path / "cache",
            )
    assert "fetch" in str(exc_info.value).lower() or "unreachable" in str(exc_info.value).lower()


@pytest.mark.unit
def test_subscribe_empty_body_raises_subscribe_error(tmp_path: Path) -> None:
    """A body with neither [[markets]]/[[stalls]] nor [[haybales]] is malformed."""
    from haywire.core.marketstall import SubscribeError, resolve_and_subscribe

    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"# empty\n"
        with pytest.raises(SubscribeError) as exc_info:
            resolve_and_subscribe(
                tmp_path / "marketplace.toml",
                "https://x.example/feed.toml",
                paste_dir=tmp_path / "stalls",
                cache_dir=tmp_path / "cache",
            )
    assert "marketplace" in str(exc_info.value).lower() or "marketstall" in str(exc_info.value).lower()


@pytest.mark.unit
def test_subscribe_pasted_block_without_haybales_raises(tmp_path: Path) -> None:
    """A pasted TOML block must contain [[haybales]] (it's a marketstall by definition)."""
    from haywire.core.marketstall import SubscribeError, resolve_and_subscribe

    block = '[[markets]]\nurl = "https://x.example/m.toml"\nignores = []\ndoubles = []\nblocked = []\n'
    with pytest.raises(SubscribeError):
        resolve_and_subscribe(
            tmp_path / "marketplace.toml",
            block,
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )

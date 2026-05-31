"""Add Source orchestrator.

The resolution algorithm composes the foundation's classify_input,
fetch_with_cache_fallback, parsers, and helpers into one pure function.
The UI dialog calls this; the function has no I/O beyond what the underlying
foundation primitives already do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import toml

from haywire.core.marketstall.cache import fetch_with_cache_fallback
from haywire.core.marketstall.errors import RemoteFetchError
from haywire.core.marketstall.helpers import (
    add_market_subscription_to_global,
    add_stall_subscription_to_global,
)
from haywire.core.marketstall.url_resolution import (
    InputForm,
    classify_input,
)


class SubscribeError(RuntimeError):
    """Raised by resolve_and_subscribe on fetch failure, malformed body, or unwriteable paste file.

    Distinct from BareRepoUrlRejectedError (which propagates separately from
    classify_input). Callers should catch both to render distinct UI messages.
    """


SubscriptionKind = Literal["market", "stall"]


@dataclass(frozen=True)
class SubscribeResult:
    """Outcome of a successful resolve_and_subscribe call.

    `kind` reports which section the subscription was written to:
      - "market" → [[markets]]
      - "stall"  → [[stalls]]
    """

    kind: SubscriptionKind
    persist_url: str
    body: str


def _derive_dist_name(toml_body: str) -> str:
    """Extract the first haybale's `name` from a pasted TOML block."""
    try:
        data = toml.loads(toml_body)
    except toml.TomlDecodeError as exc:
        raise SubscribeError(f"Pasted TOML is malformed: {exc}") from exc

    haybales = data.get("haybales", [])
    if not haybales:
        raise SubscribeError(
            "Pasted TOML block has no [[haybales]] section. A pasted block must be a marketstall."
        )
    first = haybales[0]
    name = first.get("name")
    if not isinstance(name, str) or not name:
        raise SubscribeError("First [[haybales]] entry in pasted block has no `name` field.")
    return name


_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _save_pasted_block(toml_body: str, paste_dir: Path) -> tuple[str, str]:
    """Write a pasted TOML block to paste_dir/<dist-name>.toml, return (fetch_url, persist_url)."""
    dist_name = _derive_dist_name(toml_body)
    if not _SAFE_NAME.match(dist_name):
        raise SubscribeError(
            f"Unsafe dist name {dist_name!r}; can only contain ASCII letters, digits, dot, dash, underscore."
        )

    paste_dir.mkdir(parents=True, exist_ok=True)
    out_path = paste_dir / f"{dist_name}.toml"
    out_path.write_text(toml_body, encoding="utf-8")
    file_url = f"file://{out_path.resolve()}"
    return file_url, file_url


def resolve_and_subscribe(
    global_path: Path,
    user_input: str,
    *,
    paste_dir: Path,
    cache_dir: Path | None = None,
) -> SubscribeResult:
    """Run the full Add Source algorithm.

    Raises BareRepoUrlRejectedError (propagates from classify_input) on form-3
    bare repo URLs. Raises SubscribeError on fetch failure, malformed body,
    or unwriteable paste file.
    """
    classified = classify_input(user_input)

    if classified.form is InputForm.PASTED_BLOCK:
        assert classified.toml_body is not None  # invariant of classify_input
        fetch_url, persist_url = _save_pasted_block(classified.toml_body, paste_dir)
    else:
        assert classified.fetch_url is not None and classified.persist_url is not None
        fetch_url = classified.fetch_url
        persist_url = classified.persist_url

    try:
        result = fetch_with_cache_fallback(fetch_url, cache_dir=cache_dir)
    except RemoteFetchError as exc:
        raise SubscribeError(f"Could not fetch {fetch_url}: {exc}") from exc

    body = result.body
    try:
        data = toml.loads(body)
    except toml.TomlDecodeError as exc:
        raise SubscribeError(f"Fetched body is malformed TOML: {exc}") from exc

    has_markets_or_stalls = bool(data.get("markets")) or bool(data.get("stalls"))
    has_haybales = bool(data.get("haybales"))

    if has_markets_or_stalls:
        add_market_subscription_to_global(global_path, persist_url)
        return SubscribeResult(kind="market", persist_url=persist_url, body=body)

    if has_haybales:
        add_stall_subscription_to_global(global_path, persist_url)
        return SubscribeResult(kind="stall", persist_url=persist_url, body=body)

    raise SubscribeError(
        "Body is neither a marketplace (no [[markets]] or [[stalls]]) nor a marketstall (no [[haybales]])."
    )

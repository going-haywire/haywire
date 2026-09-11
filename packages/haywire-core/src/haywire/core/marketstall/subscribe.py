"""Add Source orchestrator.

Two phases: :func:`resolve_source` works out what an input is and what it
offers without writing anything, and :func:`subscribe` commits it to the
global marketplace. :func:`resolve_and_subscribe` runs both.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import toml

from haywire.core.library.haybale import Haybale
from haywire.core.marketstall.cache import fetch_with_cache_fallback
from haywire.core.marketstall.errors import RemoteFetchError
from haywire.core.marketstall.helpers import (
    add_market_subscription_to_global,
    add_stall_subscription_to_global,
)
from haywire.core.marketstall.parsing import (
    parse_marketstall_body,
    parse_remote_marketplace_body,
)
from haywire.core.marketstall.url_resolution import (
    InputForm,
    classify_input,
)


class SubscribeError(RuntimeError):
    """Raised by resolve_and_subscribe on fetch failure, malformed body, or unwriteable paste file.

    A bare repo URL raises
    :class:`~haywire.core.marketstall.url_resolution.BareRepoUrlRejectedError`
    instead, which is not a subclass of this.
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


@dataclass(frozen=True)
class ResolvedSource:
    """What a source turned out to be, before anything is written.

    Produced by :func:`resolve_source`, consumed by :func:`subscribe`. ``kind``
    is the section subscribing would write to, and ``haybales`` is what the
    source offers.

    ``pasted_body`` is the raw TOML of a pasted block, held in memory until
    :func:`subscribe` writes it under ``paste_dir``; it is None for every URL
    form. ``persist_url`` is likewise empty for a pasted block, since its
    ``file://`` URL is only known once that file has a home.
    """

    kind: SubscriptionKind
    persist_url: str
    body: str
    haybales: list[Haybale] = field(default_factory=list)
    pasted_body: str | None = None

    @property
    def is_paste(self) -> bool:
        return self.pasted_body is not None


def _derive_dist_name(toml_body: str) -> str:
    """Extract the first haybale's `name` from a pasted TOML block.

    Raises SubscribeError on malformed TOML, no [[haybales]] section, or a
    first entry with no `name`.
    """
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


def _require_safe_name(dist_name: str) -> None:
    """Reject a pasted block whose derived filename would escape paste_dir."""
    if not _SAFE_NAME.match(dist_name):
        raise SubscribeError(
            f"Unsafe dist name {dist_name!r}; can only contain ASCII letters, digits, dot, dash, underscore."
        )


def _save_pasted_block(toml_body: str, paste_dir: Path) -> tuple[str, str]:
    """Write a pasted TOML block to paste_dir/<dist-name>.toml, return (fetch_url, persist_url)."""
    dist_name = _derive_dist_name(toml_body)
    _require_safe_name(dist_name)

    paste_dir.mkdir(parents=True, exist_ok=True)
    out_path = paste_dir / f"{dist_name}.toml"
    out_path.write_text(toml_body, encoding="utf-8")
    file_url = f"file://{out_path.resolve()}"
    return file_url, file_url


def resolve_source(
    user_input: str,
    *,
    cache_dir: Path | None = None,
) -> ResolvedSource:
    """Phase 1 — work out what *user_input* is. Writes nothing, not even a pasted block.

    Classifies the input, fetches the body or takes the pasted block, and
    decides from its shape which section subscribing would write: a body with
    [[markets]] or [[stalls]] resolves as ``"market"``, one with only
    [[haybales]] as ``"stall"``. The haybales it offers are parsed onto the
    result.

    Raises:
        BareRepoUrlRejectedError: *user_input* is a bare repo URL.
        SubscribeError: The fetch failed, the body is malformed TOML, or it is
            neither a marketplace nor a marketstall.
    """
    classified = classify_input(user_input)

    pasted_body: str | None = None
    if classified.form is InputForm.PASTED_BLOCK:
        assert classified.toml_body is not None  # invariant of classify_input
        pasted_body = classified.toml_body
        # Derive the name now, though only subscribe() uses it, so a bad block
        # fails on the read step rather than at write time.
        dist_name = _derive_dist_name(pasted_body)
        _require_safe_name(dist_name)
        body = pasted_body
        persist_url = ""  # filled in by subscribe(), which knows paste_dir
    else:
        assert classified.fetch_url is not None and classified.persist_url is not None
        persist_url = classified.persist_url
        try:
            result = fetch_with_cache_fallback(classified.fetch_url, cache_dir=cache_dir)
        except RemoteFetchError as exc:
            raise SubscribeError(f"Could not fetch {classified.fetch_url}: {exc}") from exc
        body = result.body

    try:
        data = toml.loads(body)
    except toml.TomlDecodeError as exc:
        raise SubscribeError(f"Fetched body is malformed TOML: {exc}") from exc

    has_markets_or_stalls = bool(data.get("markets")) or bool(data.get("stalls"))
    has_haybales = bool(data.get("haybales"))

    if has_markets_or_stalls:
        contents = parse_remote_marketplace_body(body)
        return ResolvedSource(
            kind="market",
            persist_url=persist_url,
            body=body,
            haybales=list(contents.haybales),
            pasted_body=pasted_body,
        )

    if has_haybales:
        return ResolvedSource(
            kind="stall",
            persist_url=persist_url,
            body=body,
            haybales=parse_marketstall_body(body),
            pasted_body=pasted_body,
        )

    raise SubscribeError(
        "Body is neither a marketplace (no [[markets]] or [[stalls]]) nor a marketstall (no [[haybales]])."
    )


def subscribe(
    resolved: ResolvedSource,
    global_path: Path,
    *,
    paste_dir: Path,
) -> SubscribeResult:
    """Phase 2 — write the subscription. The only mutation.

    For a pasted block this first writes the block to
    ``paste_dir/<dist-name>.toml`` and subscribes to the resulting ``file://``
    URL, overwriting any file already there.

    Idempotent on URL match: re-subscribing an already-present source adds no
    duplicate entry.
    """
    persist_url = resolved.persist_url
    if resolved.pasted_body is not None:
        _, persist_url = _save_pasted_block(resolved.pasted_body, paste_dir)

    if resolved.kind == "market":
        add_market_subscription_to_global(global_path, persist_url)
    else:
        add_stall_subscription_to_global(global_path, persist_url)

    return SubscribeResult(kind=resolved.kind, persist_url=persist_url, body=resolved.body)


def resolve_and_subscribe(
    global_path: Path,
    user_input: str,
    *,
    paste_dir: Path,
    cache_dir: Path | None = None,
) -> SubscribeResult:
    """Run the full Add Source algorithm: resolve, then subscribe.

    Writes unconditionally. To show what a source offers, and which names it
    would collide with, before writing anything, drive the two phases
    separately.

    Raises:
        BareRepoUrlRejectedError: *user_input* is a bare repo URL.
        SubscribeError: The fetch failed, the body is malformed, or the paste
            file could not be written.
    """
    resolved = resolve_source(user_input, cache_dir=cache_dir)
    return subscribe(resolved, global_path, paste_dir=paste_dir)

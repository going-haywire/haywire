"""Add Source input classification.

Four input forms (form 3 / bare repo URL dropped per inquisition Q4):
  1. Blob URL — host provider rewrites to raw; raw URL is both fetched and persisted.
  2. Raw URL — fetched and persisted as-is.
  3. Plain TOML URL — fetched as-is; persisted as-is.
  4. Pasted TOML block — written to ~/.haywire/db/.../stalls/<name>.toml,
     then referenced as file:// (handled by the caller after classify_input).

Persistence rule: the URL written to marketplace.toml must be directly fetchable
by the refresh pipeline (it calls fetch_with_cache_fallback on sub.url with no
re-classification). Blob URLs return HTML, so any blob input is normalized to
its raw form before persisting.

Bare repo URLs (e.g. `https://github.com/alice/cool-libs`) are rejected with a
clear error pointing at the README marker pattern.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from haywire.core.marketstall.host_providers import HOST_PROVIDERS, resolve_host


class InputForm(enum.Enum):
    """The four accepted input forms."""

    BLOB_URL = "blob_url"
    RAW_URL = "raw_url"
    PLAIN_TOML_URL = "plain_toml_url"
    PASTED_BLOCK = "pasted_block"


class BareRepoUrlRejectedError(ValueError):
    """Raised when the user pastes a bare repo URL."""


@dataclass(frozen=True)
class ClassifiedInput:
    """Output of classify_input.

    For URL forms (BLOB_URL, RAW_URL, PLAIN_TOML_URL):
      - fetch_url: the URL the runtime will HTTP-fetch
      - persist_url: the URL written into the marketplace file as the subscription key
      - toml_body: None
    For PASTED_BLOCK:
      - fetch_url: None
      - persist_url: None (caller derives file:// after writing the block to disk)
      - toml_body: the raw TOML the user pasted
    """

    form: InputForm
    fetch_url: str | None = None
    persist_url: str | None = None
    toml_body: str | None = None


_URL_LIKE = re.compile(r"^(https?|file)://", re.IGNORECASE)


def classify_input(user_input: str) -> ClassifiedInput:
    """Classify Add Source input. Raises BareRepoUrlRejectedError on form-3 URLs."""
    stripped = user_input.strip()

    if not _URL_LIKE.match(stripped):
        # Form 4: pasted TOML block.
        return ClassifiedInput(form=InputForm.PASTED_BLOCK, toml_body=user_input)

    # Strip trailing artifacts that browsers/users commonly add.
    normalized = stripped.rstrip("/")
    for suffix in (".git",):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]

    if normalized.startswith("file://"):
        return ClassifiedInput(
            form=InputForm.PLAIN_TOML_URL,
            fetch_url=normalized,
            persist_url=normalized,
        )

    parts = urlsplit(normalized)
    hostname = (parts.hostname or "").lower()
    provider = resolve_host(hostname)

    if provider is not None:
        blob = provider.parse_blob_url(normalized)
        if blob is not None:
            raw_url = provider.raw_url(blob.owner, blob.repo, blob.ref, blob.path)
            return ClassifiedInput(
                form=InputForm.BLOB_URL,
                fetch_url=raw_url,
                persist_url=raw_url,
            )

        raw = provider.parse_raw_url(normalized)
        if raw is not None:
            return ClassifiedInput(
                form=InputForm.RAW_URL,
                fetch_url=normalized,
                persist_url=normalized,
            )

        # Provider matched the hostname but URL didn't match blob or raw shape.
        # If the path looks like a bare /owner/repo, reject as form 3.
        path_parts = [p for p in parts.path.split("/") if p]
        if len(path_parts) == 2:
            raise BareRepoUrlRejectedError(
                "Paste the URL to the marketstall.toml file, not the repo. "
                f"Look for a `marketstall:share-url` block in the {hostname} repo's README."
            )

    # No provider matched by hostname — try all providers for blob/raw URL shapes.
    # This handles secondary hostnames like raw.githubusercontent.com.
    for p in HOST_PROVIDERS:
        blob = p.parse_blob_url(normalized)
        if blob is not None:
            raw_url = p.raw_url(blob.owner, blob.repo, blob.ref, blob.path)
            return ClassifiedInput(
                form=InputForm.BLOB_URL,
                fetch_url=raw_url,
                persist_url=raw_url,
            )
        raw = p.parse_raw_url(normalized)
        if raw is not None:
            return ClassifiedInput(
                form=InputForm.RAW_URL,
                fetch_url=normalized,
                persist_url=normalized,
            )

    # If it has a path that looks like /owner/repo with no further file, reject.
    path_parts = [p for p in parts.path.split("/") if p]
    if hostname in {"github.com", "gitlab.com", "bitbucket.org"} and len(path_parts) == 2:
        raise BareRepoUrlRejectedError(
            "Paste the URL to the marketstall.toml file, not the repo. "
            f"Look for a `marketstall:share-url` block in the {hostname} repo's README."
        )

    # Plain TOML URL — anything else with a path.
    return ClassifiedInput(
        form=InputForm.PLAIN_TOML_URL,
        fetch_url=normalized,
        persist_url=normalized,
    )

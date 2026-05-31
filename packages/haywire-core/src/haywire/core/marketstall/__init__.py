"""Marketstall distribution runtime.

Replaces the legacy haywire.core.marketplace + marketplace_runtime + marketplace_errors
trio. The submodules here implement the new section vocabulary ([[markets]], [[stalls]],
[[haybales]], [[heaps]], [[caches]]), the host-provider abstraction, and the URL
resolution/refresh pipeline. The directory naming reflects the future haybale-marketplace
carve-out.
"""

from haywire.core.marketstall.cache import (
    cache_read,
    cache_write,
    fetch_with_cache_fallback,
    gc_orphans,
)
from haywire.core.marketstall.errors import (
    DuplicateHeapNameError,
    MalformedMarketplaceError,
    RemoteFetchError,
)
from haywire.core.marketstall.helpers import (
    SubscriptionConflict,
    add_heap_to_project,
    add_market_subscription_to_global,
    add_stall_subscription_to_global,
    detect_subscription_conflicts,
    record_block_on_source,
    record_ignore_on_source,
    remove_stale_haybale_from_project,
    resolve_block_target,
)
from haywire.core.marketstall.parsing import (
    RemoteMarketplaceContents,
    parse_global_marketplace,
    parse_marketstall_body,
    parse_project_marketplace,
    parse_remote_marketplace_body,
    serialize_global_marketplace,
    serialize_project_marketplace,
)
from haywire.core.marketstall.platform import current_os, haybale_supports_current_os
from haywire.core.marketstall.refresh import (
    apply_blocked,
    apply_first_come_first_served,
    apply_heaps_shadow,
    apply_ignores,
    mark_stale_against_previous,
    refresh,
)
from haywire.core.marketstall.types import (
    FetchResult,
    Haybale,
    MarketplaceFile,
    ProjectMarketplaceFile,
    RefreshOutcome,
    RefreshReport,
    Subscription,
)
from haywire.core.marketstall.subscribe import (
    SubscribeError,
    SubscribeResult,
    SubscriptionKind,
    resolve_and_subscribe,
)
from haywire.core.marketstall.url_resolution import (
    BareRepoUrlRejectedError,
    ClassifiedInput,
    InputForm,
    classify_input,
)

__all__ = [
    # Dataclasses / enums
    "FetchResult",
    "Haybale",
    "MarketplaceFile",
    "ProjectMarketplaceFile",
    "RefreshOutcome",
    "RefreshReport",
    "Subscription",
    "RemoteMarketplaceContents",
    "SubscriptionConflict",
    "ClassifiedInput",
    "InputForm",
    # Parsers + serializers
    "parse_global_marketplace",
    "parse_project_marketplace",
    "parse_marketstall_body",
    "parse_remote_marketplace_body",
    "serialize_global_marketplace",
    "serialize_project_marketplace",
    # Cache
    "cache_read",
    "cache_write",
    "fetch_with_cache_fallback",
    "gc_orphans",
    # Refresh
    "refresh",
    "apply_ignores",
    "apply_blocked",
    "apply_heaps_shadow",
    "apply_first_come_first_served",
    "mark_stale_against_previous",
    # Helpers / install-safety
    "add_market_subscription_to_global",
    "add_stall_subscription_to_global",
    "add_heap_to_project",
    "remove_stale_haybale_from_project",
    "record_ignore_on_source",
    "record_block_on_source",
    "resolve_block_target",
    "detect_subscription_conflicts",
    # Errors
    "MalformedMarketplaceError",
    "DuplicateHeapNameError",
    "RemoteFetchError",
    "BareRepoUrlRejectedError",
    # Platform
    "current_os",
    "haybale_supports_current_os",
    # URL resolution
    "classify_input",
    # Add Source orchestration
    "resolve_and_subscribe",
    "SubscribeResult",
    "SubscribeError",
    "SubscriptionKind",
]

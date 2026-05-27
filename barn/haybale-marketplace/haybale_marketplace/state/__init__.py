"""App-scoped state classes contributed by haybale-marketplace.

- LibraryManagerState — publishes the LibraryManager (uv subprocess orchestration).
- MarketplaceState — marketstall file parsing and refresh orchestration.

Note: enable/disable persistence is owned by the core LibraryRegistry via
HostStore (see haywire.core.host.store); no AppState is involved.
"""

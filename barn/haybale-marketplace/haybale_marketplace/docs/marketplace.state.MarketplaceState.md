# Marketplace State

`marketplace:state:MarketplaceState` · kind: state

## Notes

Owns marketplace orchestration for the studio library.

Read API:
  - get_global(): MarketplaceFile | None (None when malformed; sets
    global_marketplace_error so the UI can render the Edit File banner).
  - get_project_haybales(): list[Haybale] from the project [[caches]].

Orchestration API:
  - refresh(): RefreshReport, runs the refresh pipeline and caches the
    report on self.last_report for the UI to display.

Path derivation (in on_enable):
  - workspace_root from haywire.core.di.context.get_workspace_root().
  - global_path = ~/.haywire/db/haybale_marketplace/marketplace.toml.
  - project_path = <workspace_root>/.haywire/marketplace.toml.

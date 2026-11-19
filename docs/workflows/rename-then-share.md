---
status: draft
doc_template: workflow
scope: W3, a library author renames a library (usually off the local-only hay- prefix) and then shares it
see-also:
  - index.md
  - ../guides/rename-library.md
---

# Rename, then share

**For:** library authors, most often moving a library off the local-only `hay-` name
before its first share.

```mermaid
sequenceDiagram
    autonumber
    actor You as Author
    participant CLI as haywire (rename, verify)
    participant Repo as Your project

    You->>CLI: haywire verify
    You->>Repo: commit everything (clean tree)
    You->>CLI: haywire rename hay-old haybale-new (dry run)
    CLI-->>You: what would change
    You->>CLI: ① the name: rename … --apply
    CLI->>Repo: library, imports, every graph
    You->>CLI: haywire verify, restart the studio
    You->>You: share: Share an update / Create and first share
```

| Step | Who | Where the rule or command lives |
|---|---|---|
| No graphs yet: create the project again instead | author | [Renaming §1](../guides/rename-library.md#1-the-short-version) |
| Verify and commit | author | [Renaming §4](../guides/rename-library.md#4-what-has-to-be-true-before-you-rename) |
| Dry run | author | [Renaming §5.1](../guides/rename-library.md#51-dry-run-the-default) |
| ① Choose the name and apply | author | [Renaming §3](../guides/rename-library.md#3-choosing-a-name), [§5.2](../guides/rename-library.md#52-applying-it) |
| Confirm, restart | author | [Renaming §5.3](../guides/rename-library.md#53-confirming-the-result) |
| Share | author | [Share an update](share-an-update.md) |

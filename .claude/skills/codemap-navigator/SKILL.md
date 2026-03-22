---
name: codemap-navigator
description: >
  Guides Claude to use the .codemap/ documentation map before reading source
  files directly. Trigger BEFORE diving into code for any task that requires
  understanding the codebase: bug fixes, features, refactoring, code review,
  architecture questions, finding definitions, understanding data flow, or
  onboarding. Also trigger on "where is", "how does X work", "what depends on",
  "find the code that", "which module". If no .codemap/ exists, suggest running
  codebase-cartographer first.
---

# Codemap Navigator

**Core rule:** Never scan the full codebase when `.codemap/` exists.
Always do the two-hop lookup below instead.

## Lookup sequence

1. **Check** — does `.codemap/INDEX.md` exist?
   If not: suggest generating one with codebase-cartographer, then fall
   back to README → CLAUDE.md → directory tree.

2. **Read INDEX.md** (≤120 lines). Identify which module(s) match the
   task. If unsure, ask the user — one question costs less than loading
   five wrong manifests.

3. **Read only the relevant module manifest(s)** from
   `.codemap/modules/{name}.md`. Each one tells you:
   - Always-load files → read these first.
   - On-demand files → read only if the task touches that area.
   - Dependencies → follow links to other manifests if needed.
   - Rules & Source of Truth → constraints and canonical files.

4. **Check `.codemap/cross-cuts/`** if the task spans multiple modules.

5. **Proceed with the task** using the source files the manifest pointed
   you to.

## Key constraints

- Never load all manifests at once. Start with 1–2, expand if needed.
- Never skip the map and grep source files directly.
- Read manifests before source files — they explain the why.
- If a manifest's "Mapped at" commit is far behind HEAD, flag staleness
  to the user but still use the map.
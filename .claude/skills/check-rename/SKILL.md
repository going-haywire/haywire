---
name: check-rename
description: >
  Find stale references in tests/, barn/, and docs/ after a class/method/file
  rename refactor. The IDE's "rename symbol" command updates Python imports
  and attribute access, but it misses string-based references — `patch("module.Symbol")`,
  `patch.object(obj, "method_name")`, `monkeypatch.setattr`, `importlib.import_module`,
  doc citations, and similar. Run this skill immediately after a rename refactor
  (especially before committing) to surface what the IDE missed and update it
  file-by-file with user confirmation. Trigger on: `/check-rename`, "I just
  renamed X", "are there leftovers from the rename", "did the IDE catch
  everything", or any rename-followup conversation.
---

# check-rename

## Why this skill exists

Symbol renames in this codebase routinely break tests because the IDE refactor only follows real Python attribute/import access, not string literals. Recent example: renaming `_open_remove_confirm_dialog` → inlined `confirm_modal` call. The IDE updated the editor, but `tests/studio/test_haystack_editor_remove.py` had six `patch.object(editor, "_open_remove_confirm_dialog")` calls that pointed at a method that no longer existed. They all failed at `patch.__enter__` time with `AttributeError`.

The patterns that break are deterministic. We can find them.

## When to run

- Right after using "Rename Symbol" in the IDE on a class, method, or module.
- After committing a refactor and being unsure whether docs/tests follow.
- When the user mentions "I renamed X" or "is there anything left referring to the old name."
- Slash command: `/check-rename` — explicit invocation.

Do **not** run for trivial local-variable renames or formatting-only changes.

## Procedure

### 1. Detect

Run the detector from the repo root:

```sh
python .claude/skills/check-rename/scripts/detect_renames.py
```

The script compares the working tree against `HEAD`, parses each changed `.py` file's AST before-and-after, infers symbol renames by name similarity (Levenshtein + structural cues like same kind/parent), and searches `tests/`, `barn/`, `docs/` for remnants of every removed name. It also detects renamed *files* via `git status -M` and looks for stale references to the old module path.

It prints a JSON document on stdout with two top-level arrays:

- `symbol_renames` — each entry has `old`, `new`, `file`, `kind`, `confidence`, and a list of `remnants` (file/line/snippet).
- `file_renames` — each entry has `old_path`, `new_path`, `old_module`, `module_remnants`, and `path_remnants`.

### 2. Filter and confirm

Not every entry is a real rename:

- **Low confidence (< 0.5) AND no remnants** — drop silently. Probably an unrelated removal.
- **Low confidence AND remnants exist** — the script couldn't pair an "added" symbol to this removal, but the old name still appears elsewhere. Surface to the user as "removed symbol still referenced" rather than as a rename. Ask the user what the new name should be (if any) before searching further.
- **High confidence (≥ 0.5) AND remnants exist** — the candidate case. Show old → new, the file where it was renamed, and the list of remnants.
- **High confidence AND zero remnants** — nothing for the user to do; mention briefly so they know it was checked.

For each surviving candidate, present in this shape:

```
Renamed: <old> → <new>   (in <file>, confidence <pct>)
Found <N> remnants:
  <relpath>:<line>  <snippet>
  ...
```

Group remnants by file for the next step.

### 3. Update, one file at a time

For each file that contains remnants, ask the user a single yes/no:

> Update `tests/foo/bar.py`? It contains <N> occurrences of `<old>` that should become `<new>`.

If yes, replace word-boundary matches of the old name with the new one in that file. Use the Edit tool with `replace_all` only when every occurrence in the file is the same symbol — if any line in the file uses the old name in a different sense (a string literal that happens to share the name, an unrelated comment), edit those occurrences individually after re-reading the file.

After each batch, run the relevant tests for the touched file as a sanity check:

```sh
uv run pytest <file_that_was_updated> -q
```

If they fail, show the failure and ask before continuing.

### 4. Final report

After all decisions are made, summarize:

- Renames detected: N
- Files updated: M
- Files skipped: K (and why, if the user gave reasons)
- Tests still failing (if any)

Suggest the user run `uv run pytest -q --ignore=tests/integration` to confirm the broader suite is still clean. Don't run the full suite unprompted — it's slow and the user can decide.

## Edge cases and judgment calls

**Pair score ties.** When two added symbols are equally similar to a removed one (e.g. removed `update` could plausibly match either `apply` or `commit`), the detector picks one but mentions the ambiguity. Confirm with the user before applying.

**Reused names.** If `confirm_modal` was renamed away in one file but is still defined elsewhere (e.g. it's a library function with a new local wrapper), the global occurrence count won't drop to zero. The detector reports the global count; if remnants are found but the global count is still high, the "rename" is probably a local change — confirm with the user before mass-editing.

**Doc files.** Docs cite symbols in prose (`` `OldName` ``) and code blocks. The detector finds both. Be conservative when editing docs — surrounding prose may need rephrasing, not just a word swap. For doc updates, prefer showing the diff and asking the user rather than auto-editing.

**File renames vs. symbol renames inside the renamed file.** If a file was both renamed *and* its contents changed, the script reports both. Handle the file rename first (update import paths), then re-run if needed to catch any leftover symbol renames.

**False positives from unrelated removals.** Deleting a method and adding a totally different one in the same file will be flagged as a rename candidate. Low confidence + irrelevant new name is the signal — drop and move on.

## What this skill does NOT do

- Update `packages/haywire-core` or `packages/haywire-studio`. The IDE handles these reliably; scanning them adds noise. If you need to update those, do it through the IDE.
- Detect renames of local variables, parameters, or imports-as-aliases. Only top-level `def`/`class` and methods on top-level classes.
- Run automatic full-suite tests. The skill targets the test files it touched, but a full re-run is the user's call.
- Handle renames inside `.venv`, `node_modules`, or other vendored directories.

---
name: curate-trim-examples
description: Search the codebase for docstrings that make better calibration examples for the trim-docs skill, and add or replace entries in its examples.md.
argument-hint: "[path]"
disable-model-invocation: true
---

# Curate trim-docs examples

`.claude/skills/trim-docs/examples.md` shows the trim-docs skill what a good rewrite looks like, and trim-docs copies what it sees. Improve that file using real code under `$ARGUMENTS`, or the whole repository if no path is given. Edit only that file.

## What makes a good example

Score every candidate on these five criteria:

1. **Verified.** You read the code, and every fact in the rewrite is true. A candidate that fails this is rejected.
2. **Teaches a judgment.** The most useful docstrings mix contract and rationale, so the right rewrite keeps something that looks like rationale (a timing guarantee an overrider must respect) or drops something that looks like contract (a restatement of another class's behavior).
3. **Typical.** The pattern shows up often in the scan results, so the lesson transfers to many files.
4. **Compact.** The old docstring is under about 25 lines, and the rewrite fits the length guide in `.claude/rules/python-docs.md`.
5. **Stable.** It's in core code that won't churn soon. Skip tests, generated code, vendored code, and anything deprecated.

## Categories

Every entry has exactly one of these categories, named in its heading:

- User-facing class
- Protocol or abstract base
- Overridable method
- Public method
- Private helper
- Rationale moved to a line comment
- Long comment trimmed to a constraint
- Comment with history
- Describes another component
- Module docstring
- Leave alone
- Scan false positive

Whether the app displays a docstring is not a category but a property of the entry, recorded in its `Displayed` line. Displayed entries follow the Markdown rules in the standard's Markup section; the rest use reST. Keep at least one displayed entry in the file.

"Leave alone" is a docstring that is long or over the limit but is all contract, so the right action is to change nothing or almost nothing. "Scan false positive" is a docstring the scan flags that is fine as written. These two stop trim-docs from over-trimming, so fill them early.

Allow at most 2 entries per category and 16 in total, and keep the file under about 300 lines.

## Steps

1. Read `.claude/rules/python-docs.md`, `.claude/skills/trim-docs/SKILL.md`, and `examples.md`. Note which categories are empty, which entries are unverified, and what each entry's `Teaches` line covers.
2. Re-check existing entries if the standard changed. Find the last commit that touched `examples.md` (`git log -1 --format=%h -- .claude/skills/trim-docs/examples.md`) and run `git diff <that commit> -- .claude/rules .claude/skills`. If anything changed, re-check every entry, verified or not, against the current versions, including that its category is still in the list and its `Displayed` line and markup are right. A `Source` pin records where an entry came from; it doesn't freeze the entry. Correct entries the current standard says are wrong and keep the pin. Corrections don't count toward the change limit, but list each one in the report.
3. Verify existing entries. For each unverified entry, find its symbol in the code. If the code is still in its old form, or you can recover it with `git log -S "<symbol>" -p`, correct the rewrite to match the code and replace the `Source` line with the path, symbol, and short commit hash. If you can't find the code, leave the entry as it is and treat it as the first thing to replace in its category.
4. Gather 15 to 25 candidates from these sources:
   - `python .claude/skills/trim-docs/docstring_audit.py scan $ARGUMENTS --top 60`.
   - A spread across packages: read a few flagged items from each package, not only the top of the list, so typical cases compete with extreme ones.
   - Over-limit docstrings without flags, as candidates for "Leave alone".
   - Findings whose flags are wrong, as candidates for "Scan false positive".
   - Displayed docstrings: registered components, and anything found with `rg -n "__doc__|getdoc\(" --type py`.
   - Past cleanup commits, found with `git log --oneline --grep="docs: trim docstrings"`. Their diffs are reviewed before-and-after pairs. A later commit that edits a docstring a cleanup commit rewrote is the strongest signal of all, because it shows where trim-docs got it wrong. Prefer these, and use the corrected version as the rewrite.
5. For each candidate, read the code and at least one caller or implementer, assign a category, write the rewrite following the standard, and score it against the five criteria.
6. Decide what to do with each candidate:
   - **Add** it if its category has fewer than 2 entries and the file has fewer than 16.
   - **Replace** an entry in the same category if the candidate is verified and the entry isn't, or if the candidate is clearly better on criteria 2, 3, or 4. Name the criterion in the report.
   - **Remove** an entry that duplicates the example in `.claude/rules/python-docs.md`, or when you need room to stay within the line budget, as long as its category keeps at least one entry.
   - Otherwise, reject the candidate.

   Make at most 4 adds or replaces per run so the change stays reviewable. Removals don't count toward that limit, but each needs a reason in the report. Never leave a category empty that had an entry before.
7. Write each new entry in the format below, and keep the file's header accurate. Once no unverified entries remain, remove the sentence about them.
8. Check the rewrites. Copy every Python block in `examples.md` into its own file in a temporary directory outside the repository, then run `scan` on that directory. Every block must parse. These findings are expected:
   - caps flags for names defined elsewhere in the repository, such as `INT`;
   - a length finding on a "Leave alone" entry, with no phrasing flags;
   - on a "Scan false positive" entry, the flag its `Teaches` line names.

   Any other finding means the rewrite doesn't follow the standard. Fix it before committing.
9. Commit only `examples.md`, with the message `docs(trim-docs): update calibration examples`.

## Entry format

````markdown
## <Category>: `<symbol>`

Source: <path/to/file.py>::<Class.method> at <short commit hash>
Displayed: <yes (Markdown) | no (reST)>
Teaches: <the one judgment this entry demonstrates, in a sentence>

```python
<the rewritten docstring, plus any comments at the lines they explain>
```

Removed: <what came out, summarized in a sentence or two>
Kept: <what stayed and why the caller needs it>
````

When a displayed docstring contains its own fenced code block, wrap the entry's code in a four-backtick fence (````` ````python `````) so the inner fence doesn't close it, and extract it that way in the scan check.

A "Leave alone" entry shows the docstring as it stands and uses `Removed: nothing` or names the one small change. A "Scan false positive" entry names the flag in its `Teaches` line.

## Rules

- Edit only `examples.md`. Don't change source code, the standard, or the trim-docs skill.
- Every rewrite must follow the standard exactly, including its Markup section, because trim-docs imitates it. If a candidate shows that the standard is ambiguous or wrong, don't work around it in an example. Report it.
- Don't paste old docstrings into the file. Summarize them in the `Removed` line; the originals stay in git history.

## Report

- Each add or replace: category, symbol, the entry it replaced, and the criterion that decided it.
- Existing entries you verified or corrected.
- Categories that are still empty.
- Notable rejected candidates, one line each.
- Places where the standard seemed ambiguous.

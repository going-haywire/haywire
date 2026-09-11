---
name: trim-docs
description: Rewrite verbose docstrings and comments under a path so they follow the project's docstring standard. Changes only docstrings and comments.
argument-hint: "[path]"
disable-model-invocation: true
---

# Trim docstrings and comments

Bring the docstrings and comments under `$ARGUMENTS` in line with the standard in `.claude/rules/python-docs.md`. Change nothing except docstrings and comments.

## 1. Prepare

1. Read `.claude/rules/python-docs.md` and `.claude/skills/trim-docs/examples.md`. The examples set the target shape and length.
2. Find out which docstrings the app displays. Every registered component's class docstring is displayed; locate the registration mechanism, and use `rg -n "__doc__|getdoc\(" --type py` to find anything else that reads docstrings. Displayed docstrings follow the Markdown rules in the standard's Markup section. List every one you change in the report.
3. Check whether doctests run (`--doctest-modules` or `doctest` in pytest config, tox, nox, or CI). If they do, keep examples runnable.
4. Run `git status`. The working tree must be clean so verification compares only your changes.
5. Build the worklist:
   `python .claude/skills/trim-docs/docstring_audit.py scan $ARGUMENTS`
   It lists docstrings and comment blocks over the length guide or containing flagged phrasing (history words, argumentative words, ALL-CAPS emphasis), worst first. Flags are hints: some are false positives, and the scan misses things, so read every docstring in each file you touch.

## 2. Work in batches

- One package (directory) per batch and one commit per batch, with the message `docs: trim docstrings in <package>`.
- Order: public API first (what users of the framework touch), then protocols and base classes, then internals.
- On the first run in this repository, stop after 3 to 5 files and show the diff for review before continuing.

## 3. Rewrite each docstring

1. Read the code, and at least one caller or implementer, until you know what it does. Never write a claim you haven't confirmed in the code.
2. Sort every sentence of the old docstring and act on it:

| The sentence is | Do this |
|---|---|
| Contract: behavior, arguments, return value, exceptions, side effects, observable edge cases, guarantees implementers must keep | Keep; rewrite it plainly |
| The reason a specific line is non-obvious | Move it to a one- or two-line present-tense comment on that line |
| History: what it used to be, what changed | Delete |
| Design argument or rejected alternative | Delete; if it's architectural and no ADR covers it, add a notes entry (step 6) |
| Behavior of another component | Replace with a reference, or delete |
| Narration of the implementation | Delete |
| Explains what a plain-typed, `dict`, `Any`, or union argument or return value means | Keep, as an `Args:` or `Returns:` entry |
| Names an exception and when it's raised | Keep, as a `Raises:` entry |
| Usage example | Keep every correct one; fix wrong ones and format them per the standard |
| Restates what a framework type or a clear name already says | Delete |
| Describes callers | Delete |

3. Write the new docstring: a one-line summary, then only what the caller needs, then the `Args:`, `Returns:`, `Raises:` sections and the example the standard asks for. If an argument the standard says to document is unexplained, add its entry, using only facts you've confirmed in the code. If the example misses a typical use, add it, taking usage from the tests or real call sites. Compare the result with `examples.md` for shape and length.
4. If you can't tell whether a sentence is contract or rationale, keep a short version and list it in the report.

## 4. Rewrite each comment

Sort comments the same way. Rewrite what you keep in the present tense and cut it to one or two lines. Delete comments that restate the code. Leave `# TODO`, `# noqa`, `# type: ignore`, `# pragma`, license headers, and similar markers unchanged.

## 5. Rules

- Change only docstrings and comments. No renames, reformatting, moved code, or new docstrings on undocumented code.
- Follow the standard's Markup section: Markdown for displayed docstrings, reST for the rest. When a displayed docstring is written in reST, convert it.
- A docstring that is still over the length guide after you've removed everything but contract is done. Don't cut contract to meet the guide.
- Keep everything a caller needs: `None` returns, exceptions, side effects, units, valid ranges, threading and call-timing guarantees.
- Don't invent behavior to fill a summary.

## 6. Verify and commit each batch

1. `python .claude/skills/trim-docs/docstring_audit.py verify <package>` checks that the code, with docstrings and comments ignored, is identical to `HEAD`. Fix every file it reports.
2. Run the test suite, and doctests if the project uses them.
3. If the project builds docs with Sphinx, build them and fix any new warnings.
4. Rerun `scan` on the package and deal with what remains, or note why a finding stays.
5. Commit.

Design reasoning worth an ADR goes in `docs/docstring-cleanup-notes.md`: one entry per topic with the file and symbol and a two- or three-sentence summary. Skip anything an existing ADR in `docs/adr/` already covers. The original wording stays in git history, so don't copy it in.

## 7. Report after each batch

- Files changed and roughly how many docstring and comment lines were removed.
- Runtime-visible docstrings you changed.
- Sentences you kept because you weren't sure they were contract.
- Arguments that needed an `Args:` entry only because the name or type hint is vague. These are rename or retyping candidates; don't change them yourself.
- Docstrings that contradict the signature (for example, an accepted type the hint doesn't include). Keep whichever the code confirms, and list them.
- Notes entries you added.

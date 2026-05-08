# Coverage classifier — subagent prompt

When [SKILL.md](SKILL.md)'s coverage phase finds a doc page with no META section (via `check_coverage.py`), dispatch an `Explore` subagent with the prompt below to classify the doc and propose its source list. The user approves before `update_meta.py` runs.

## How to use

For each uncovered doc path returned by `check_coverage.py`:

1. Dispatch `Explore` subagent with the [prompt template](#prompt-template) below, filling in `<DOC_PATH>` (the absolute path to the doc).
2. Receive the verdict (R or N) and proposed source list.
3. **Verify** every proposed source path exists at HEAD (`ls` or `test -f`). The subagent occasionally proposes plausible paths that don't exist — never trust without verifying.
4. **Sanity-check** the proposal against the calibration rules below. The subagent has a known bias to over-cite (see "calibration" section). Trim or adjust before showing the user.
5. Show the user the final proposal (verdict + sources), with a brief reasoning summary. Wait for approval.
6. On approval: run `update_meta.py --create <doc> <sources...>` for R, or `update_meta.py --no-review <doc>` for N.

Do **not** auto-apply without user approval. Coverage decisions are editorial — the subagent and the verification are advisory; the user owns the call.

## Prompt template

Copy this verbatim into the `Agent` invocation. Replace `<DOC_PATH>` with the absolute path of the uncovered doc.

```
I'm classifying a documentation page for a freshness-tracking system in
the Haywire repo. For ONE doc page, decide between three outcomes:

  R (review-needed) — the doc makes claims about source-code behaviour
    that would be FALSIFIED if specific source files changed.
    Falsifiable claims include:
      - Enumerated lists of enum members ("NodeType has values
        DATA, CONTROL, EVENT, OUTPUT, LOOPBACK").
      - Specific .value strings for enum members ("REQUIRED = 'required'").
      - Documented signatures, return types, or parameter names.
      - Specific class names whose deletion or rename would invalidate
        the doc's vocabulary (e.g. "the @library decorator").
      - Specific file paths or module locations the doc points at.
      - Concrete behavioural claims tied to a named function or
        method ("FlowAssemblyManager._process_callback_edges()
        wires CALLBACK edges at assembly time").

  N (no-review-needed) — the doc has no source-code dependencies that
    a code change could falsify, AND THE DOC IS COMPLETE AS IT IS.
    Examples:
      - Pure prose, vocabulary, design rules, navigation.
      - Mentions of code paths in passing, where the doc makes NO
        specific assertion about what's in those files.
      - Architectural description that names systems but does not
        document their signatures or members.
    N means "permanent exemption from review" — the doc's design
    is to make no falsifiable claims.

  P (pending) — the doc EXISTS but is a placeholder, stub, or
    work-in-progress that has not yet developed enough content
    to evaluate. The doc may eventually become R (when content is
    written) or N (if the finished doc has no source claims).
    Examples:
      - Empty file or a single-line "TODO" / "coming soon".
      - Outline with section headings but no body text.
      - Frontmatter-only with no real content.
      - Less than ~10 lines of actual prose.
    P is NOT for short docs that are intentionally short — those
    are N (a one-paragraph perspective landing page may be
    intentionally minimal). P is for INCOMPLETE docs.

BIAS HARD TOWARD N when uncertain between R and N. The freshness
check is about catching wrong claims, not tracking name-drops.
A doc that names a class but only describes it conceptually does
NOT need an R verdict for that file.

When uncertain between N and P: if the doc clearly intends to say
more later (TODO, "coming soon", obvious gaps), it's P. If the doc
reads as complete-as-intended, it's N.

For an R verdict, propose a NARROW source list. Include a file ONLY
if the doc makes a concrete falsifiable claim about its content.
RULES:
  1. Do NOT include a file just because the doc names a class
     in passing without making any specific assertion about it.
     A doc that says "the system uses LibraryRegistry to track
     plugins" makes no falsifiable claim — that's a name-drop.
     A doc that says "LibraryRegistry exposes register(name, lib)"
     IS making a claim, and the file is tracked.
  2. INCLUDE a file when the doc enumerates enum members, .value
     strings, or other content that lives literally in the file.
  3. INCLUDE a file when the doc cites a specific method, attribute,
     or signature by name AND describes its behaviour, return shape,
     parameters, or invariants.
  4. INCLUDE a file even if another doc page also tracks it.
     Different docs make different claims about the same source.
     If a glossary entry lists NodeType members AND node-canon
     describes the role of each, BOTH track node/behavior.py —
     each catches a different kind of drift. Duplication across
     docs is the point: every doc whose claim a code change would
     falsify must track that source.

Source path conventions for this repo:
  - Framework code:  packages/haywire-core/src/haywire/core/...
  - Studio code:     packages/haywire-studio/src/haywire_studio/...
  - UI code:         packages/haywire-core/src/haywire/ui/...
  - Library plugins: barn/haybale-*/haybale_*/...

For every proposed source path, give the FULL repo-relative path.
Do NOT propose paths you have not opened or verified — when unsure
where a class/enum lives, grep for its definition first.

The doc to evaluate:

  <DOC_PATH>

Return EXACTLY this format:

  verdict: R, N, or P
  reasoning: 2-3 sentences. For R, name the strongest concrete claim
             the doc makes that justifies tracking. For N, name what
             the doc IS (vocabulary, navigation, design rules) that
             makes review unnecessary AND complete-as-intended. For P,
             name what's missing or stub-shaped about the doc.
  sources:   one path per line, OR omit entirely if N or P.

Be honest about uncertainty. If the doc is borderline R/N, lean N. If
the doc is borderline N/P, prefer P when there's any sign of
incompleteness — a false-P just means the doc is re-checked next run,
which is harmless; a false-N permanently exempts a stub from review.

Report under 250 words.
```

## Calibration

The prompt is tuned by tested examples. Two notes from the calibration run:

### Subagent bias: over-citing by class-name presence

In testing against `docs/reference/glossary.md`, the subagent initially proposed 11 source files because the glossary *names* 11 classes. After tightening, the correct list was 8 — three files (assembly manager, interpreter, execution context) were dropped because the glossary only **named** those classes, while the deeper claims about them live in dedicated architecture-arch docs that track those same files.

The classifier prompt now contains explicit rules (1, 4, 5) to counter this bias. When reviewing subagent output, double-check: does each proposed source correspond to a SPECIFIC FALSIFIABLE CLAIM, or just a name-drop? If just a name-drop, drop it.

### Subagent gap: missing files where claims are most concrete

In the same glossary test, the subagent missed `packages/haywire-core/src/haywire/ui/editor/identity.py` — even though the glossary documents `OpenBehavior` enum members AND their `.value` strings (the most concrete kind of claim). The subagent had been searching `haywire/core/` and missed `haywire/ui/`.

When reviewing subagent output, scan the doc yourself for ENUM MEMBER lists or LITERAL STRING values — these are the highest-confidence R signals. If the proposal doesn't include the file holding those, add it.

### Heuristic for the user-side review

After verifying paths exist, ask yourself:

  1. For each proposed source: "If this file's tree-hash changed, would the doc page be wrong?"
     - Yes  → keep
     - No   → drop
     - Maybe → drop unless this is the doc's primary subject

  2. Scan the doc for enum lists, literal strings, signature claims:
     - Is the file holding those in the proposed list?
     - If not, add it.

This is the editorial step. The subagent's job is to surface candidates; the user's job is to apply the "specific falsifiable claim" test.

## Worked examples

### Example 1: docs/reference/glossary.md (R, narrow)

The glossary enumerates `NodeType` members, `FlowType` members, `OpenBehavior` members + .value strings, and names `BaseLibrary`/`LibraryRegistry`/`LibraryDiscovery`/`LibraryIdentity`/`FileWatcher`. It mentions `FlowAssemblyManager`, `Interpreter`, `ExecutionContext` only as qualified names ("performed by `FlowAssemblyManager`") — those are tracked by `assembly-arch.md`, `virtual-machine-arch.md`, etc., not by the glossary.

```
verdict: R
sources:
  packages/haywire-core/src/haywire/core/node/behavior.py
  packages/haywire-core/src/haywire/core/types/enums.py
  packages/haywire-core/src/haywire/core/library/base.py
  packages/haywire-core/src/haywire/core/library/registry.py
  packages/haywire-core/src/haywire/core/library/discovery.py
  packages/haywire-core/src/haywire/core/library/identity.py
  packages/haywire-core/src/haywire/core/library/file_watcher.py
  packages/haywire-core/src/haywire/ui/editor/identity.py
```

### Example 2: docs/architecture/execution/callbacks/callbacks-arch.md (R)

This is an architecture doc with concrete claims about specific methods (`FlowAssemblyManager._process_callback_edges()`), runtime behavior (`CallbackManager` dispatch), and return shapes (`Interpreter.get_statistics()` keys). All four files are correctly tracked here.

```
verdict: R
sources:
  packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py
  packages/haywire-core/src/haywire/core/execution/callback_manager.py
  packages/haywire-core/src/haywire/core/execution/interpreter.py
  packages/haywire-core/src/haywire/core/execution/event_source.py
```

### Example 3: docs/reference/design-guide.md (N — hypothetical)

A design guide is UX rules and CSS token conventions. Even if it names CSS classes (`hw-panel`, `hw-slot-bar-tabs`), those live in CSS files and the doc's job is design intent, not tracking literal source. N.

```
verdict: N
reasoning: Design guide documents UX rules and CSS token conventions.
           Mentions CSS classes by name but makes no falsifiable
           source-code claim; design intent is the artifact, not the
           CSS source.
```

### Example 4: docs/welcome/user/index.md (N — hypothetical)

Perspective landing pages are pure navigation. They link to canon docs but make no source claims of their own. N.

### Example 5: docs/architecture/studio/workspace/workspace-arch.md (P — placeholder)

An arch doc with a frontmatter block, an h1, and a single TODO sentence. The doc INTENDS to document the workspace system but doesn't yet make any falsifiable claim. P, not N — N would permanently exempt it; P keeps the skill checking each run until real content lands.

```
verdict: P
reasoning: Doc has only frontmatter and a "TODO: document the workspace
           lifecycle" stub. No falsifiable claims yet. Re-classify when
           content is added.
```

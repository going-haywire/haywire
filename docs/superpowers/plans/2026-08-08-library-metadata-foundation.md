# Library Metadata Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `LibraryIdentity` and `Haybale` a shared `LibraryMetadata` base so the
library detail view renders from one field list regardless of whether a library is
online, installed, or a local heap — and make marketstall rows carry *coordinates*
(`origin` + `install_spec` + repo-relative paths) that consumers resolve through
`HostProvider`, instead of URLs baked at publish time.

**Architecture:** A new `LibraryMetadata` dataclass holds the fifteen fields both
classes carry; each becomes a subclass adding its own concerns. Three apparent
divergences are reconciled first (`on_reload` to `str`, `linked_libraries` to module
names, `version` semantics documented), because the base cannot be honest until they
are. `docs_path`/`examples_path`/`tests_path` hold **repo-relative paths from the
commit they first appear** — the resolution machinery lands in the same plan rather
than leaving a field whose name contradicts its contents.

**Tech Stack:** Python 3.12, dataclasses, `importlib.metadata`, tomlkit
(`haywire.core.tomlio.edit_toml`), pytest.

## Global Constraints

- Line length 109 (`uv run ruff check .` **and** `uv run ruff format --check .` — CI runs both).
- Type-check with the exact command in `CLAUDE.md`; `haybale-visiongraph` is excluded.
- Gate before every commit: `uv run pytest -m "not browser and not perf"` (~2.5 min).
- Never call `create_test_injector()` directly in a test — use the `test_injector` fixtures.
- Barn `__init__.py` files use **double quotes** (`ruff format` output). Any regex
  touching decorator source must be quote-agnostic.
- `_TOML_FIELDS` controls marketstall serialization; `to_dict()` omits falsy values.
- **No field may coexist with the field that replaces it**, and no field's name may
  contradict its contents. This is the ADR's whole point; a rename that outruns its
  semantics reintroduces the split in a new form.

## Source Documents

- Decision record: [ADR 0024](../../adr/0024-library-metadata-single-source.md)
- Design + full 10-step migration: 2026-08-08-library-metadata-consolidation.md

This plan implements migration **steps 1–5**: the metadata shape and the
coordinate-based marketstall row. Steps 6–10 follow in separate plans — see
"Out of scope" below and the Spec Coverage note at the end. **This plan does not
by itself reach the consolidation's goal**: the duplicated fields (`version`,
`description`, `author`, `tags`) are still authored twice until step 7.

## The end state this plan reaches

A marketstall row carries **coordinates**, not URLs:

```toml
[[haybales]]
name = "haybale-core"
origin = "https://github.com/going-haywire/haywire"
install_spec = "haybale-core @ git+https://github.com/going-haywire/haywire.git@v0.0.40#subdirectory=barn/haybale-core"
docs_path     = "barn/haybale-core/haybale_core/"
examples_path = "barn/haybale-core/examples/OVERVIEW.md"
tests_path    = "barn/haybale-core/tests/"
```

Consumers assemble what they need — `origin` says which repo, `install_spec` which
commit, `*_path` which file:

```python
provider = resolve_host(urlparse(pkg.origin).hostname)
owner, repo = provider.parse_origin(pkg.origin)
_, ref, _ = _parse_git_install_spec(pkg.install_spec)

fetch_from = provider.raw_url(owner, repo, ref, pkg.examples_path)
link_to    = provider.blob_url(owner, repo, ref, pkg.examples_path)
```

A trailing slash means directory (`tree_url`, and fetchers append
`OVERVIEW.md`/`QUICKREF.md`); no slash means file (`blob_url`).

Why: the ref then lives in exactly **one** place, so no two fields can disagree
about which commit was published; raw-vs-rendered stops being a stored decision, so
`_clickable_doc_url` is deleted rather than reimplemented; a self-hosted host
resolves against the *reader's* config rather than the publisher's; and host rules
live in `HostProvider` alone instead of the three places that re-encode them today.

## Out of scope — the follow-up plans, in dependency order

The consolidation doc numbers these 6–10, but that numbering predates this plan
and is **not** a build order. Written as dependencies actually fall:

**Next — step 7: `LibraryIdentity` reads distribution metadata.** Depends on this
plan's base class. Drops `version`/`description`/`author`/`author_url`/`url`/`tags`
from the decorator and reads them from `importlib.metadata`; adds `os`,
`examples_path`, `tests_path` as decorator kwargs; renames the decorator's
`dependencies` → `linked_libraries`; makes `id` required. **This is the step that
ends the duplication** — until it lands, those four fields are still authored in
both files. Everything below depends on it.

**Then these three — all need step 7's decorator kwargs to exist. 9 and 6 are
independent of each other; 8 wants 6 already in place:**

- **step 9: one decorator reader, one generator.** Promotes the AST reader out of
  `scripts/generate_marketstall.py` into `haywire.core.publishing`, widened to
  every decorator field a row needs. Deletes `_read_library_label`,
  `_read_library_dependencies`, and **the regex helper Task 5 Step 8 introduces**.
  Converges `generate_marketstall.build_entry` onto
  `pyproject + decorator → LibraryMetadata → Haybale → TOML`, fixing two
  divergences from the share pipeline on the way.
- **step 6: declared-path preconditions.** A declared `examples_path`/`tests_path`
  that does not exist on disk fails `check_preconditions` with a `fix_id`
  (`clear_examples_path` / `set_examples_path`) and a resolve modal, alongside
  `strip_os`/`add_origin`. Needs the paths to be *authored declarations* first,
  which is why it cannot precede step 7.
- **step 8: metadata editing moves into the Share flow.** Adds an `edit` screen
  between `preflight` and `review`; deletes `_overview_edit_dialog.py` and
  `LibraryManager.update_library_identity` — and with them **Task 1's fix**, which
  is temporary by design. Best done after step 6 so the path fields it edits can
  validate inline against a precondition that already exists.

**Last — step 10: author-facing migration.** All 10 barn `__init__.py` +
`pyproject.toml` pairs to the target surface, the `haywire init` scaffold, the
`haywire rename` CLI, docs, and `uv run haywire docs --all`. Last because every
field needs its final home before the libraries are rewritten to match.

Suggested order: **7 → 9 → 6 → 8 → 10**.

## File Structure

| File | Responsibility |
| --- | --- |
| `packages/haywire-core/src/haywire/core/library/metadata.py` | **new** — `LibraryMetadata` base dataclass |
| `packages/haywire-core/src/haywire/core/library/identity.py` | `LibraryIdentity` extends the base; `LibraryReloadAction` unchanged |
| `packages/haywire-core/src/haywire/core/marketstall/types.py` | `Haybale` extends the base; six superseded field names removed (see Task 4) |
| `packages/haywire-core/src/haywire/core/marketstall/parsing.py` | parse the base fields; old keys removed outright |
| `packages/haywire-core/src/haywire/core/marketstall/refresh.py:179-181` | carry the renamed fields across a cache refresh |
| `packages/haywire-core/src/haywire/core/marketstall/host_providers/base.py` | `HostProvider` gains `tree_url()` and `parse_origin()` |
| `packages/haywire-core/src/haywire/core/marketstall/host_providers/github.py` | implement both |
| `packages/haywire-core/src/haywire/core/marketstall/host_providers/gitlab.py` | implement both |
| `packages/haywire-core/src/haywire/core/marketstall/locate.py` | **new** — `resolve_row_path()`: the one place a row + path becomes a URL |
| `packages/haywire-core/src/haywire/core/publishing/marketstall.py` | producer emits relative paths; `_folder_url` deleted |
| `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py` | consumers resolve; `_clickable_doc_url` deleted |
| `barn/haybale-marketplace/haybale_marketplace/state/marketplace_state.py` | `fetch_overview` resolves; `_github_raw_base` deleted |
| `barn/haybale-marketplace/haybale_marketplace/library_manager.py` | quote-bug fix (Task 1) |
| `tests/core/test_library/test_metadata.py` | **new** — base-class and subclass field coverage |
| `tests/core/test_library/test_reload_action.py` | **new** — `on_reload` str/enum round-trip |
| `tests/marketstall/test_locate.py` | **new** — row + path → raw/blob/tree URL, both hosts |
| `tests/marketplace/test_update_identity_quoting.py` | **new** — regression test for Task 1 |

---

### Task 1: Fix the silently-no-oping identity writer

`update_library_identity` rewrites five decorator fields with regexes that match
**single quotes only** (`(    label=')[^']*(')`). Every barn library is
`ruff format`ted to double quotes, so all five writes silently do nothing. The
quote-agnostic helper already exists three lines below in the same function.

This task is independent of the rest of the plan and ships on its own. Step 8 of
the migration eventually deletes this call site, but the bug is live today and the
migration is long.

**Files:**

- Modify: `barn/haybale-marketplace/haybale_marketplace/library_manager.py:986-990`
- Test: `tests/marketplace/test_update_identity_quoting.py` (create)

**Interfaces:**

- Consumes: `haywire.core.library.decorator_io._set_decorator_str_field(content: str, field: str, value: str) -> str` — already quote-agnostic (`['\"]`), already used for `on_reload` at line 993.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Write the failing test**

Create `tests/marketplace/test_update_identity_quoting.py`:

```python
"""The identity writer must handle double-quoted decorators — which is all of them.

Regression test: the original implementation used single-quote-only regexes
(`(    label=')[^']*(')`), so every write silently no-opped against
`ruff format` output.
"""

import pytest

from haywire.core.library.decorator_io import _set_decorator_str_field

DOUBLE_QUOTED = '''from haywire.core.library.decorator import library


@library(
    label="Old Label",
    id="demo",
    description="Old description",
    url="https://old.example",
    author="Old Author",
    author_url="https://old-author.example",
    file_watcher=True,
)
class Library:
    pass
'''


@pytest.mark.parametrize(
    "field,new_value",
    [
        ("label", "New Label"),
        ("description", "New description"),
        ("url", "https://new.example"),
        ("author", "New Author"),
        ("author_url", "https://new-author.example"),
    ],
)
def test_set_decorator_str_field_rewrites_double_quoted(field, new_value):
    result = _set_decorator_str_field(DOUBLE_QUOTED, field, new_value)
    assert f'{field}="{new_value}"' in result


def test_rewrite_leaves_other_fields_untouched():
    result = _set_decorator_str_field(DOUBLE_QUOTED, "label", "New Label")
    assert 'id="demo"' in result
    assert 'author="Old Author"' in result
    assert "file_watcher=True" in result


def test_rewrite_is_idempotent():
    once = _set_decorator_str_field(DOUBLE_QUOTED, "label", "X")
    twice = _set_decorator_str_field(once, "label", "X")
    assert once == twice
```

- [ ] **Step 2: Run the test to see which parts already pass**

Run: `uv run pytest tests/marketplace/test_update_identity_quoting.py -v`

Expected: **all PASS.** `_set_decorator_str_field` is already correct — this test
pins the helper's behavior so the swap in Step 3 is provably safe. The bug is in
`library_manager`'s failure to *use* it, which Step 4 covers.

- [ ] **Step 3: Replace the five inline regexes**

In `barn/haybale-marketplace/haybale_marketplace/library_manager.py`, replace lines
986-990:

```python
            content = re.sub(r"(    label=')[^']*(')", rf"\g<1>{label_val}\2", content)
            content = re.sub(r"(    description=')[^']*(')", rf"\g<1>{desc_val}\2", content)
            content = re.sub(r"(    url=')[^']*(')", rf"\g<1>{url_val}\2", content)
            content = re.sub(r"(    author=')[^']*(')", rf"\g<1>{author_val}\2", content)
            content = re.sub(r"(    author_url=')[^']*(')", rf"\g<1>{author_url_val}\2", content)
```

with:

```python
            content = _set_decorator_str_field(content, "label", label_val)
            content = _set_decorator_str_field(content, "description", desc_val)
            content = _set_decorator_str_field(content, "url", url_val)
            content = _set_decorator_str_field(content, "author", author_val)
            content = _set_decorator_str_field(content, "author_url", author_url_val)
```

Add to the imports at the top of the file, beside the existing
`_set_decorator_list_field` import:

```python
from haywire.core.library.decorator_io import _set_decorator_str_field
```

Check whether `re` is still used elsewhere in the file before removing its import:

Run: `grep -n "re\.\(sub\|search\|match\|findall\|compile\)" barn/haybale-marketplace/haybale_marketplace/library_manager.py`

If that returns no results, remove `import re` from the file's imports. If it
returns results, leave the import alone.

- [ ] **Step 4: Add the end-to-end test**

Append to `tests/marketplace/test_update_identity_quoting.py`:

```python
def test_update_library_identity_writes_double_quoted_decorator(tmp_path):
    """End-to-end: the manager's write path must land on a double-quoted file."""
    from unittest.mock import MagicMock

    from haybale_marketplace.library_manager import LibraryManager

    pkg_dir = tmp_path / "barn" / "haybale-demo" / "haybale_demo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text(DOUBLE_QUOTED)
    (pkg_dir.parent / "pyproject.toml").write_text(
        '[project]\nname = "haybale-demo"\nversion = "0.1.0"\n'
    )

    registry = MagicMock()
    registry.get_library_distribution_name.return_value = "haybale-demo"
    manager = LibraryManager.__new__(LibraryManager)
    manager.registry = registry

    ok, message = manager.update_library_identity(
        "demo",
        str(tmp_path),
        {
            "label": "Fresh Label",
            "description": "Fresh description",
            "url": "https://fresh.example",
            "author": "Fresh Author",
            "author_url": "https://fresh-author.example",
            "tags": ["alpha"],
            "dependencies": [],
            "on_reload": "none",
        },
    )

    assert ok, message
    written = (pkg_dir / "__init__.py").read_text()
    assert 'label="Fresh Label"' in written
    assert 'description="Fresh description"' in written
    assert 'author="Fresh Author"' in written
    assert 'author_url="https://fresh-author.example"' in written
    assert "Old Label" not in written
```

- [ ] **Step 5: Run the new test**

Run: `uv run pytest tests/marketplace/test_update_identity_quoting.py -v`

Expected: PASS. If `LibraryManager.__init__` requires more attributes than
`registry`, the `MagicMock` construction will raise `AttributeError` naming the
missing one — add it to the `__new__`-constructed instance and re-run.

- [ ] **Step 6: Run the marketplace suite for regressions**

Run: `uv run pytest tests/marketplace/ -q`

Expected: all pass.

- [ ] **Step 7: Lint, format, type-check**

```bash
uv run ruff check barn/haybale-marketplace/ tests/marketplace/
uv run ruff format --check barn/haybale-marketplace/ tests/marketplace/
uv run mypy barn/haybale-marketplace/haybale_marketplace/
```

Expected: clean. Anything new is yours.

- [ ] **Step 8: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/library_manager.py \
        tests/marketplace/test_update_identity_quoting.py
git commit -m "fix(marketplace): identity writer no-opped on double-quoted decorators

The five inline regexes matched single quotes only; every barn library is
ruff-formatted to double quotes, so label/description/url/author/author_url
edits silently did nothing. Swap to the quote-agnostic helper already used
for on_reload in the same function."
```

---

### Task 2: Delete the dead `help_url` field

`help_url` has **zero readers** repo-wide. Its role was taken by the marketstall's
generated `docs_url`. Removing it before the base class exists keeps the base's
field list honest.

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/library/identity.py:71`
- Modify: `packages/haywire-core/src/haywire/core/library/decorator.py` (docstring: lines 32, 75)
- Modify: `packages/haywire-core/src/haywire/core/library/utils.py:77`
- Modify: `packages/haywire-core/src/haywire/core/settings/registry.py:43`
- Modify: `packages/haywire-core/src/haywire/ui/themes/registry.py:23`
- Modify: `packages/haywire-studio/src/haywire_studio/init.py:381`
- Modify: all 10 `barn/*/[a-z_]*/__init__.py` that pass `help_url=`

**Interfaces:**

- Consumes: nothing.
- Produces: `LibraryIdentity` no longer accepts `help_url`. Task 3 assumes it is gone.

- [ ] **Step 1: Confirm there are still no readers**

```bash
grep -rn "help_url" --include="*.py" packages/ barn/ tests/ scripts/ | grep -v "DataTypeIdentity\|types/identity\|types/decorator\|types/interface"
```

Expected: only **assignments** (`help_url=""`), never a read
(`.help_url`, `identity.help_url`, `["help_url"]`).

`DataTypeIdentity.help_url` is a **different field on a different class** and stays.
If any line in the filtered output reads a `LibraryIdentity.help_url`, stop and
report — the premise of this task is wrong.

- [ ] **Step 2: Remove the field and every assignment**

In `packages/haywire-core/src/haywire/core/library/identity.py`, delete line 71:

```python
    help_url: str
```

In `packages/haywire-core/src/haywire/core/library/utils.py`, delete from the
fallback `LibraryIdentity(...)` construction:

```python
        help_url="auto-generated",
```

Delete the `help_url=""` line from each of:

- `packages/haywire-core/src/haywire/core/settings/registry.py` (line ~43)
- `packages/haywire-core/src/haywire/ui/themes/registry.py` (line ~23)
- `packages/haywire-studio/src/haywire_studio/init.py` (line ~381, the scaffold template string)

In `packages/haywire-core/src/haywire/core/library/decorator.py`, delete the
docstring line:

```text
        help_url (str, optional): URL to documentation. Defaults to empty string.
```

and the `help_url=...` line from the "Full customization" example.

Then every barn library:

```bash
grep -rln "help_url" barn/*/[a-z_]*/__init__.py
```

Remove the `help_url="..."` line from each file listed.

- [ ] **Step 3: Verify no assignments remain**

```bash
grep -rn "help_url" --include="*.py" packages/ barn/ scripts/ | grep -v "types/identity\|types/decorator\|types/interface"
```

Expected: no output. (`DataTypeIdentity.help_url` is filtered out and stays.)

- [ ] **Step 4: Run the full suite**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/help_url.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/help_url.log
```

Expected: `exit=0`, no FAILED lines.

No new test for this task — the field has no readers, so there is no behavior to
pin. A construction site still passing `help_url=` raises `TypeError` and the
traceback names the file; that is what the suite run above is checking.

- [ ] **Step 5: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(library)!: drop the dead help_url identity field

Zero readers repo-wide; its role was taken by the marketstall's generated
docs_url. DataTypeIdentity.help_url is a different field and is untouched."
```

---

### Task 3: Reconcile `on_reload` to the wire form

`LibraryIdentity.on_reload` is a `LibraryReloadAction`; `Haybale` will carry the
plain `str` that TOML and farmhand JSON already use. The base needs one type. Take
`str` — it is the on-disk form — and keep the enum reachable through a property so
the ordering (`max()` across libraries) survives.

Do this before the base class exists so Task 4 is a pure move.

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/library/identity.py:84-99`
- Test: `tests/core/test_library/test_reload_action.py` (create)

**Interfaces:**

- Consumes: `LibraryReloadAction` (`NONE`/`REFRESH`/`RESTART`, ordered, `StrEnum`).
- Produces:
  - `LibraryIdentity.on_reload: str` — the wire value, e.g. `"restart"`.
  - `LibraryIdentity.reload_action -> LibraryReloadAction` — property; use this for
    comparison and `max()`. Task 4 moves both onto the base unchanged.

- [ ] **Step 1: Find every reader**

```bash
grep -rn "\.on_reload" --include="*.py" packages/ barn/ tests/
```

Record the list. Each site either compares to the enum (`is LibraryReloadAction.X`,
`max(...)`) — becomes `.reload_action` — or reads the value for display/serialization
(`.on_reload.value`) — becomes plain `.on_reload`.

- [ ] **Step 2: Write the failing test**

Create `tests/core/test_library/test_reload_action.py`:

```python
"""on_reload is stored in its wire form; the enum is reachable for ordering."""

import pytest

from haywire.core.library.identity import LibraryIdentity, LibraryReloadAction


def _identity(**overrides):
    base = dict(
        label="Demo",
        version="0.1.0",
        description="",
        url="",
        author="",
        author_url="",
        folder_path="/tmp/demo",
        module_name="haybale_demo",
        id="demo",
    )
    base.update(overrides)
    return LibraryIdentity(**base)


def test_on_reload_is_a_plain_string():
    identity = _identity(on_reload="restart")
    assert identity.on_reload == "restart"
    assert type(identity.on_reload) is str


def test_default_is_none_wire_value():
    assert _identity().on_reload == "none"


def test_enum_input_is_normalised_to_its_value():
    identity = _identity(on_reload=LibraryReloadAction.REFRESH)
    assert identity.on_reload == "refresh"
    assert type(identity.on_reload) is str


@pytest.mark.parametrize("raw", ["NONE", " Restart ", "refresh"])
def test_case_and_whitespace_are_normalised(raw):
    assert _identity(on_reload=raw).on_reload == raw.strip().lower()


def test_reload_action_returns_the_enum():
    assert _identity(on_reload="restart").reload_action is LibraryReloadAction.RESTART


def test_reload_action_supports_max_across_libraries():
    """Combining declarations is max() — the reason the enum is still reachable."""
    actions = [_identity(on_reload=v).reload_action for v in ("none", "restart", "refresh")]
    assert max(actions) is LibraryReloadAction.RESTART


def test_unknown_value_raises_at_construction():
    with pytest.raises(ValueError):
        _identity(on_reload="explode")
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/core/test_library/test_reload_action.py -v`

Expected: FAIL — `test_on_reload_is_a_plain_string` reports the value is a
`LibraryReloadAction`, and `test_reload_action_returns_the_enum` reports
`AttributeError: 'LibraryIdentity' object has no attribute 'reload_action'`.

- [ ] **Step 4: Change the field and add the property**

In `packages/haywire-core/src/haywire/core/library/identity.py`, replace the
`on_reload` declaration and its `__post_init__` coercion.

Field declaration (was `on_reload: LibraryReloadAction = LibraryReloadAction.NONE`):

```python
    on_reload: str = LibraryReloadAction.NONE.value
    """What the user must do after this library is installed, updated, or
        uninstalled. Stored in the wire form (``"none"``/``"refresh"``/``"restart"``)
        so it is identical on ``Haybale``, in TOML, and in farmhand JSON. Use
        :attr:`reload_action` to compare or combine declarations."""
```

In `__post_init__`, replace the coercion block:

```python
        # Validate and normalise to the wire form. Accepts the enum or any
        # case/whitespace variant of its value; an unknown value raises here
        # rather than at the next library import.
        self.on_reload = LibraryReloadAction(str(self.on_reload).strip().lower()).value
```

Add the property to the class:

```python
    @property
    def reload_action(self) -> LibraryReloadAction:
        """The ordered enum form. Use for comparison and ``max()``; the stored
        field is a plain string so both metadata shapes agree."""
        return LibraryReloadAction(self.on_reload)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/core/test_library/test_reload_action.py -v`

Expected: all PASS.

- [ ] **Step 6: Update every reader found in Step 1**

For each site recorded in Step 1:

- comparison or `max()` → `.reload_action`
- `.on_reload.value` → `.on_reload`
- `.on_reload` passed to something expecting the enum → `.reload_action`

Then confirm nothing still treats the field as an enum:

```bash
grep -rn "on_reload\.value\|on_reload is LibraryReloadAction\|on_reload ==" --include="*.py" packages/ barn/ tests/
```

Expected: no output. (`on_reload == "restart"` against a string is fine, but this
grep is conservative — inspect anything it prints.)

- [ ] **Step 7: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/reload.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/reload.log
```

Expected: `exit=0`, no FAILED lines.

- [ ] **Step 8: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(library): store on_reload in its wire form

LibraryIdentity.on_reload becomes str so it matches the value Haybale, TOML
and farmhand JSON already carry. LibraryReloadAction stays reachable via the
new reload_action property, which is what the install flow's max() needs."
```

---

### Task 4: Extract `LibraryMetadata` and rebase both classes

The payoff. Fifteen fields move to a shared base; `LibraryIdentity` and `Haybale`
each keep only what is theirs. The detail renderer can then take a
`LibraryMetadata` and work for a row, an installed library, or a heap.

**Files:**

- Create: `packages/haywire-core/src/haywire/core/library/metadata.py`
- Modify: `packages/haywire-core/src/haywire/core/library/identity.py`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/types.py:14-77`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/parsing.py:42-63`
- Test: `tests/core/test_library/test_metadata.py` (create)

**Interfaces:**

- Consumes: `LibraryReloadAction`, and `reload_action` from Task 3.
- Produces:
  - `haywire.core.library.metadata.LibraryMetadata` — dataclass, fifteen fields, all
    defaulted, plus the `reload_action` property.
  - `LibraryIdentity(LibraryMetadata)` — adds `id`, `folder_path`, `module_name`,
    `file_watcher`.
  - `Haybale(LibraryMetadata)` — adds `name`, `require`, `source`, `install_spec`,
    `origin`, plus routing/cache fields. **No longer has** `dependencies`,
    `author`, `source_url`, `docs_url`, `examples_url`, or `tests_url` — the base
    supplies every replacement.

**Note on scope — this is a breaking change, no deprecation aliases.**

Two of `Haybale`'s current fields are **superseded by base fields** and are simply
deleted from the subclass — the base already provides the replacement:

| deleted from `Haybale` | provided by `LibraryMetadata` |
| --- | --- |
| `dependencies: list[str]` | `linked_libraries: list[str]` — distinguishes it from `[project] dependencies`, which means something else entirely |
| `author: str` | `authors: list[str]` |

One is a genuine rename, because `origin` is `Haybale`-only and not on the base:

- `source_url` → `origin`

A marketstall file written before this lands loses those three values when parsed:
`_parse_haybale` will not find the old keys and the fields take their defaults.
Accepted — the feed is regenerated on every publish, and carrying both spellings is
the duplication this ADR exists to remove.

Three more are replaced **name and meaning together**, in Task 5 — the value
becomes a repo-relative path and every consumer resolves it through
`HostProvider`:

| deleted from `Haybale` | provided by `LibraryMetadata` |
| --- | --- |
| `docs_url` | `docs_path` |
| `examples_url` | `examples_path` |
| `tests_url` | `tests_path` |

Task 4 introduces the base (so `Haybale` gains the `*_path` names); Task 5 lands
the producer, the resolver, and the consumers in one commit. Between the two the
`*_path` fields are simply unpopulated — never populated with something their name
denies.

Net: **no field coexists with its replacement, and no field's name outruns its
contents.**

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_library/test_metadata.py`:

```python
"""LibraryMetadata is the shape both the runtime identity and the feed row share.

The detail renderer takes the base, so a field present on one subclass and absent
from the other would force it to branch — which is what this base exists to avoid.
"""

from dataclasses import fields

from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.metadata import LibraryMetadata
from haywire.core.marketstall.types import Haybale

SHARED_FIELDS = {
    "label",
    "version",
    "description",
    "authors",
    "tags",
    "linked_libraries",
    "on_reload",
    "os",
    "docs_path",
    "examples_path",
    "tests_path",
    "homepage_url",
    "documentation_url",
    "author_url",
    "issues_url",
}


def test_base_carries_exactly_the_shared_fields():
    assert {f.name for f in fields(LibraryMetadata)} == SHARED_FIELDS


def test_identity_extends_the_base():
    assert issubclass(LibraryIdentity, LibraryMetadata)
    assert SHARED_FIELDS <= {f.name for f in fields(LibraryIdentity)}


def test_haybale_extends_the_base():
    assert issubclass(Haybale, LibraryMetadata)
    assert SHARED_FIELDS <= {f.name for f in fields(Haybale)}


def test_identity_adds_its_own_concerns():
    own = {f.name for f in fields(LibraryIdentity)} - SHARED_FIELDS
    assert {"id", "folder_path", "module_name", "file_watcher"} <= own


def test_haybale_adds_its_own_concerns():
    own = {f.name for f in fields(Haybale)} - SHARED_FIELDS
    assert {"name", "require", "source", "install_spec", "origin"} <= own


def test_haybale_carries_no_duplicate_spellings():
    """The base's fields must not sit beside the ones they replace.

    Not an absence check for its own sake — a subclass redeclaring `authors` as
    `author`, or keeping `dependencies` next to `linked_libraries`, silently
    shadows the base and reintroduces the split this base exists to close.
    """
    names = {f.name for f in fields(Haybale)}
    superseded = {
        "dependencies",  # -> linked_libraries
        "author",  # -> authors
        "source_url",  # -> origin
        "docs_url",  # -> docs_path
        "examples_url",  # -> examples_path
        "tests_url",  # -> tests_path
    }
    assert not (superseded & names)


def test_every_base_field_defaults():
    """Dataclass inheritance requires it, and it is why LibraryIdentity's
    previously-required fields become optional."""
    assert LibraryMetadata() is not None


def test_a_renderer_can_read_either_shape_through_the_base():
    def render(meta: LibraryMetadata) -> tuple[str, str, list[str]]:
        return meta.label, meta.version, meta.authors

    identity = LibraryIdentity(
        id="demo", label="Demo", version="1.0.0", authors=["Ada"], folder_path="/tmp"
    )
    row = Haybale(name="haybale-demo", label="Demo", version="1.0.0", authors=["Ada"])

    assert render(identity) == render(row) == ("Demo", "1.0.0", ["Ada"])


def test_linked_libraries_holds_module_names_on_both():
    """Module names are the authored form; pip-name conversion happens at the
    point of use, not in the metadata."""
    identity = LibraryIdentity(id="d", linked_libraries=["haybale_studio"])
    row = Haybale(name="haybale-d", linked_libraries=["haybale_studio"])
    assert identity.linked_libraries == row.linked_libraries == ["haybale_studio"]


def test_reload_action_available_on_both():
    from haywire.core.library.identity import LibraryReloadAction

    assert Haybale(name="x", on_reload="restart").reload_action is LibraryReloadAction.RESTART
    assert LibraryIdentity(id="x", on_reload="refresh").reload_action is LibraryReloadAction.REFRESH
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/core/test_library/test_metadata.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'haywire.core.library.metadata'`.

- [ ] **Step 3: Create the base**

Create `packages/haywire-core/src/haywire/core/library/metadata.py`:

```python
"""The metadata a library carries, independent of where it is being read from.

Two shapes extend this: :class:`~haywire.core.library.identity.LibraryIdentity`
(a library loaded in this process) and
:class:`~haywire.core.marketstall.types.Haybale` (a library offered by a feed).
They describe the same library at different moments, so the library detail view
takes a ``LibraryMetadata`` and renders either without branching.

Every field defaults. Dataclass inheritance requires it — a non-default field
cannot follow a defaulted one — and the practical effect is that a partially
populated identity no longer fails at construction. The decorator populates
these regardless.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from haywire.core.library.reload import LibraryReloadAction


@dataclass
class LibraryMetadata:
    """Fields common to a loaded library and a published feed row."""

    label: str = ""
    version: str = ""
    """For an identity this is the installed version; for a feed row, the one the
    publisher advertised. They differ only while an update is pending — which is
    the transient the library browser's update badge exists to observe."""

    description: str = ""
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    linked_libraries: list[str] = field(default_factory=list)
    """Sibling haybales whose classes this library subscribes to, as **module
    names** (``haybale_studio``). Required for hot-reload: without the
    declaration a subscriber holds a stale class reference after a reload.
    Consumers needing pip names convert at the point of use."""

    on_reload: str = LibraryReloadAction.NONE.value
    """Wire form — ``"none"``, ``"refresh"``, or ``"restart"``. Use
    :attr:`reload_action` to compare or combine."""

    os: list[str] = field(default_factory=list)
    """Platforms this library supports. Empty means all. Gates installation."""

    docs_path: str = ""
    """Where the library's docs live, as a path from the **git root** of the
    repository named by ``Haybale.origin`` — e.g.
    ``"barn/haybale-core/haybale_core/"``.

    A trailing slash means a directory (link with ``tree_url``; fetchers append
    ``OVERVIEW.md``/``QUICKREF.md``); no slash means a file (``blob_url``).
    Never an absolute URL: the host and ref come from ``origin`` and
    ``install_spec``, so a baked URL could contradict them. Resolve with
    :func:`haywire.core.marketstall.locate.resolve_row_path`.

    Publish-time only — an installed library's docs travel in the wheel, so this
    is empty on a runtime-constructed identity."""

    examples_path: str = ""
    """Path from the git root to the library's examples. See :attr:`docs_path`."""

    tests_path: str = ""
    """Path from the git root to the library's tests. See :attr:`docs_path`."""

    homepage_url: str = ""
    documentation_url: str = ""
    author_url: str = ""
    issues_url: str = ""

    @property
    def reload_action(self) -> LibraryReloadAction:
        """The ordered enum form of :attr:`on_reload`, for comparison and ``max()``."""
        return LibraryReloadAction(self.on_reload)
```

- [ ] **Step 4: Move `LibraryReloadAction` to break the import cycle**

`metadata.py` needs `LibraryReloadAction`, and `identity.py` will import
`metadata.py` — so the enum cannot stay in `identity.py`.

Create `packages/haywire-core/src/haywire/core/library/reload.py` and move the
`LibraryReloadAction` class, the `_RELOAD_ACTION_RANK` dict, and its `_rank`
property/comparison methods into it verbatim from `identity.py` (currently lines
1-60), with this module docstring:

```python
"""What a library change demands of the user after install, update, or uninstall.

Lives apart from identity.py so LibraryMetadata can import it without a cycle.
"""
```

In `identity.py`, delete those lines and re-export for backward compatibility —
`LibraryReloadAction` is imported from `haywire.core.library.identity` in several
places, and this keeps them working:

```python
from haywire.core.library.metadata import LibraryMetadata
from haywire.core.library.reload import LibraryReloadAction

__all__ = ["LibraryIdentity", "LibraryMetadata", "LibraryReloadAction"]
```

- [ ] **Step 5: Rebase `LibraryIdentity`**

In `identity.py`, replace the `LibraryIdentity` dataclass body so it extends the
base and keeps only its own fields:

```python
@dataclass
class LibraryIdentity(LibraryMetadata):
    """A library as loaded in this process.

    Adds the live wiring — registry key, on-disk location, watch flag — to the
    metadata every shape carries.
    """

    id: str = ""
    """Unique identifier within the studio; prefixes every component's registry key."""

    folder_path: str = ""
    """Path to the library's module directory. Set by the decorator."""

    module_name: str = ""
    """Python module name. Set by the decorator."""

    file_watcher: bool = False
    """Watch this library's files and hot-reload on change. Development only."""

    def __post_init__(self):
        # Validate and normalise to the wire form. Accepts the enum or any
        # case/whitespace variant of its value; an unknown value raises here
        # rather than at the next library import.
        self.on_reload = LibraryReloadAction(str(self.on_reload).strip().lower()).value
```

Delete the old `dependencies`, `tags`, and `on_reload` field declarations and the
`None`-coercion lines in `__post_init__` — `field(default_factory=list)` on the base
means they are never `None`.

**`dependencies` → `linked_libraries` is a rename**, not a deletion. Find and update
every site:

```bash
grep -rn "identity\.dependencies\|dependencies=\[" --include="*.py" packages/ barn/ tests/ | grep -v "project.*dependencies"
```

Each `LibraryIdentity(...)`/`@library(...)` use of `dependencies=` becomes
`linked_libraries=`. Leave `[project] dependencies` in TOML alone — different thing.

- [ ] **Step 6: Rebase `Haybale`**

In `packages/haywire-core/src/haywire/core/marketstall/types.py`, make `Haybale`
extend the base. Delete the declarations the base now provides (`label`,
`version`, `description`, `tags`, `os`), delete the two superseded fields
(`dependencies`, `author`), and rename `source_url` → `origin`:

```python
from haywire.core.library.metadata import LibraryMetadata


@dataclass
class Haybale(LibraryMetadata):
    """One entry from a [[haybales]] section — a library as offered by a feed."""

    name: str = ""
    # The framework requirement as a full PEP 508 token, identical in shape to
    # the library's own pyproject entry: "haywire-core>=0.0.31",
    # "haywire-core~=0.0.31,<1.0.0", or the bare "haywire-core" when the author
    # deliberately declared no floor. Empty means undeclared — a state distinct
    # from the bare name, which is why this carries the package name and not
    # just the specifier. Derived from the library's pyproject at write time,
    # never authored independently. See haywire.core.marketstall.requirement.
    require: str = ""
    source: str = "pypi"
    install_spec: str = ""
    origin: str = ""
    """The repository this library is published from. Base that other locations
    resolve against; renamed from ``source_url``."""
    # Runtime-only routing metadata (not persisted).
    source_label: str = ""
    source_file: str = ""
    source_origin: str = ""
    # Cache-only fields (project [[caches]] only).
    via: str = ""
    last_seen: str = ""
    stale: bool = False
```

Note `source_origin` is **unrelated** to the new `origin` — it is runtime routing
("did this row come from a market or a stall") and is not persisted. Leave it.

Then update every reader of the three changed fields:

```bash
grep -rn "\.source_url\|\.docs_url\|\.examples_url\|\.tests_url\|\.dependencies\|pkg\.author\b\|haybale\.author\b" \
  --include="*.py" packages/ barn/ tests/ scripts/ | grep -v "project.*dependencies\|identity\.dependencies"
```

- `Haybale.source_url` → `.origin` (install-safety modal, `collect_overview_links`,
  `_install_flow/panels.py`, `fetch_overview`'s GitHub heuristic, `refresh.py:179`)
- `Haybale.docs_url`/`examples_url`/`tests_url` — **do not rewire the consumers
  here.** Leave `collect_overview_links`, `_clickable_doc_url`,
  `marketplace_state.fetch_overview` and `catalog_tools.py:178` reading the fields
  they read today; Task 5 replaces them wholesale along with the producer. Task 4
  only removes the old *declarations* from `Haybale`, so these sites will not
  compile until Task 5 — which is why **Tasks 4 and 5 land as one commit**
  (Task 4 Step 12 defers the commit; Task 5 Step 9 makes it).
- `Haybale.dependencies` → `.linked_libraries`
- `Haybale.author` → `.authors`, which is a **list** — display sites need
  `", ".join(pkg.authors)` or equivalent, not the bare value.

Replace `_TOML_FIELDS` wholesale — the three removed names go, the base's arrive:

```python
    _TOML_FIELDS: ClassVar[tuple[str, ...]] = (
        "name",
        "label",
        "version",
        "require",
        "description",
        "authors",
        "source",
        "install_spec",
        "tags",
        "os",
        "on_reload",
        "linked_libraries",
        "origin",
        "docs_path",
        "examples_path",
        "tests_path",
        "homepage_url",
        "documentation_url",
        "author_url",
        "issues_url",
        "via",
        "last_seen",
        "stale",
    )
```

`to_dict()` omits falsy values, so a field nothing populates yet stays out of the
written file.

`name` and `version` were required positionally before. Both now default to `""`,
so `_parse_haybale`'s explicit missing-field validation (`parsing.py:36-41`) becomes
the only guard — leave it exactly as it is.

- [ ] **Step 7: Update the parser**

In `packages/haywire-core/src/haywire/core/marketstall/parsing.py`, `_parse_haybale`
constructs the `Haybale`. Remove the three lines reading the deleted keys:

```python
        author=raw.get("author", ""),
        dependencies=list(raw.get("dependencies", [])),
        source_url=raw.get("source_url", ""),
        docs_url=raw.get("docs_url", ""),
        examples_url=raw.get("examples_url", ""),
        tests_url=raw.get("tests_url", ""),
```

and add the replacements plus the other new base fields:

```python
        authors=list(raw.get("authors", [])),
        linked_libraries=list(raw.get("linked_libraries", [])),
        origin=raw.get("origin", ""),
        on_reload=raw.get("on_reload", "none"),
        docs_path=raw.get("docs_path", ""),
        examples_path=raw.get("examples_path", ""),
        tests_path=raw.get("tests_path", ""),
        homepage_url=raw.get("homepage_url", ""),
        documentation_url=raw.get("documentation_url", ""),
        author_url=raw.get("author_url", ""),
        issues_url=raw.get("issues_url", ""),
```

**No fallback to the old keys.** A pre-existing marketstall file loses those six
values on parse; the feed is regenerated on every publish.

Also check `refresh.py:179-181`, which copies fields from a previous cache entry
(`source_url=prev.source_url, ...`) — update it to `origin=prev.origin` and add the
new base fields it should carry forward.

- [ ] **Step 8: Run the metadata tests**

Run: `uv run pytest tests/core/test_library/test_metadata.py -v`

Expected: all PASS.

- [ ] **Step 9: Run the library suites**

```bash
uv run pytest tests/core/test_library/ tests/core/test_libraries/ -q
```

Expected: all pass. Failures here are almost always a construction site using a
now-renamed field (`dependencies=` on an identity) — the traceback names it.

- [ ] **Step 10: Confirm the expected breakage, and only that**

```bash
uv run pytest tests/marketstall/ tests/marketplace/ -q 2>&1 | tail -30
```

Expected: **failures**, all of the form `AttributeError: 'Haybale' object has no
attribute 'docs_url'` (or `examples_url`/`tests_url`) from
`collect_overview_links`, `_clickable_doc_url`, `fetch_overview`, and
`catalog_tools`.

This is the one task in the plan that does not end green. `Haybale` has lost the
three `*_url` declarations and nothing populates `*_path` yet — Task 5 does both.
Any failure **not** about those three attributes is a real regression: fix it here.

Do not commit. Task 4 and Task 5 form one commit; go straight to Task 5.

---

### Task 5: Rows carry coordinates — resolution through `HostProvider`

The end state. The producer writes repo-relative paths; a single resolver turns a
row plus a path into whichever URL the caller needs; three consumers stop
constructing URLs by hand.

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/marketstall/host_providers/base.py`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/host_providers/github.py`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/host_providers/gitlab.py`
- Create: `packages/haywire-core/src/haywire/core/marketstall/locate.py`
- Modify: `packages/haywire-core/src/haywire/core/publishing/marketstall.py:118-149`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:119-145`
- Modify: `barn/haybale-marketplace/haybale_marketplace/state/marketplace_state.py:198-280`
- Modify: `barn/haybale-marketplace/haybale_marketplace/farmhands/catalog_tools.py:178`
- Test: `tests/marketstall/test_locate.py` (create)

**Interfaces:**

- Consumes: `Haybale.origin`, `.install_spec`, `.docs_path`, `.examples_path`,
  `.tests_path` from Task 4; `resolve_host(hostname) -> HostProvider | None`.
- Produces:
  - `HostProvider.parse_origin(url: str) -> tuple[str, str] | None` — `(owner, repo)`.
  - `HostProvider.tree_url(owner, repo, ref, path) -> str`.
  - `haywire.core.marketstall.locate.resolve_row_path(row, path, *, form) -> str | None`
    where `form` is `"raw"`, `"blob"`, or `"tree"`. `None` when the host is
    unrecognised or the row lacks `origin`/`install_spec`.

- [ ] **Step 1: Write the failing resolver test**

Create `tests/marketstall/test_locate.py`:

```python
"""A row carries coordinates; locate turns them into whichever URL a caller needs."""

import pytest

from haywire.core.marketstall.locate import resolve_row_path
from haywire.core.marketstall.types import Haybale

GH = Haybale(
    name="haybale-core",
    origin="https://github.com/going-haywire/haywire",
    install_spec=(
        "haybale-core @ git+https://github.com/going-haywire/haywire.git"
        "@v0.0.40#subdirectory=barn/haybale-core"
    ),
    docs_path="barn/haybale-core/haybale_core/",
    examples_path="barn/haybale-core/examples/OVERVIEW.md",
)

GL = Haybale(
    name="haybale-core",
    origin="https://gitlab.com/group/sub/haywire",
    install_spec=(
        "haybale-core @ git+https://gitlab.com/group/sub/haywire.git"
        "@v0.0.40#subdirectory=barn/haybale-core"
    ),
    examples_path="barn/haybale-core/examples/OVERVIEW.md",
)


def test_github_raw_url():
    assert resolve_row_path(GH, GH.examples_path, form="raw") == (
        "https://raw.githubusercontent.com/going-haywire/haywire/v0.0.40/"
        "barn/haybale-core/examples/OVERVIEW.md"
    )


def test_github_blob_url_for_a_file():
    assert resolve_row_path(GH, GH.examples_path, form="blob") == (
        "https://github.com/going-haywire/haywire/blob/v0.0.40/"
        "barn/haybale-core/examples/OVERVIEW.md"
    )


def test_github_tree_url_for_a_directory():
    assert resolve_row_path(GH, GH.docs_path, form="tree") == (
        "https://github.com/going-haywire/haywire/tree/v0.0.40/"
        "barn/haybale-core/haybale_core/"
    )


def test_gitlab_nested_group_origin_parses():
    """GitLab owners can be nested; the repo is the last segment."""
    assert resolve_row_path(GL, GL.examples_path, form="raw") == (
        "https://gitlab.com/group/sub/haywire/-/raw/v0.0.40/"
        "barn/haybale-core/examples/OVERVIEW.md"
    )


def test_ref_comes_from_install_spec_not_origin():
    """The commit is named in exactly one place, so nothing can contradict it."""
    row = Haybale(
        name="x",
        origin="https://github.com/o/r",
        install_spec="x @ git+https://github.com/o/r.git@v9.9.9#subdirectory=libs/x",
        docs_path="libs/x/docs/",
    )
    assert "/v9.9.9/" in resolve_row_path(row, row.docs_path, form="raw")


def test_unknown_host_yields_none_rather_than_a_wrong_url():
    row = Haybale(
        name="x",
        origin="https://git.example.invalid/o/r",
        install_spec="x @ git+https://git.example.invalid/o/r.git@v1#subdirectory=x",
        docs_path="x/docs/",
    )
    assert resolve_row_path(row, row.docs_path, form="raw") is None


@pytest.mark.parametrize("row", [Haybale(name="x"), Haybale(name="x", origin="https://github.com/o/r")])
def test_missing_coordinates_yield_none(row):
    assert resolve_row_path(row, "some/path", form="raw") is None


def test_empty_path_yields_none():
    assert resolve_row_path(GH, "", form="raw") is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/marketstall/test_locate.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'haywire.core.marketstall.locate'`.

- [ ] **Step 3: Extend the `HostProvider` Protocol**

In `host_providers/base.py`, add two members to the `HostProvider` Protocol,
after `blob_url`:

```python
    def tree_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Construct the browser URL for a *directory*.

        Distinct from :meth:`blob_url` because hosts route files and directories
        differently — GitHub uses /blob/ and /tree/, GitLab /-/blob/ and /-/tree/.
        """
        ...

    def parse_origin(self, url: str) -> tuple[str, str] | None:
        """Split a bare repository URL into ``(owner, repo)``. None if not a match.

        The existing parse_* methods take blob/raw URLs, which carry a ref and a
        path; a row's ``origin`` has neither, so it needs its own parser.
        """
        ...
```

- [ ] **Step 4: Implement both on GitHub**

In `host_providers/github.py`, add to `GitHubProvider`:

```python
_GITHUB_ORIGIN_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


    def tree_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://github.com/{owner}/{repo}/tree/{ref}/{path}"

    def parse_origin(self, url: str) -> tuple[str, str] | None:
        m = _GITHUB_ORIGIN_RE.match(url.strip())
        return (m.group("owner"), m.group("repo")) if m else None
```

Put `_GITHUB_ORIGIN_RE` at module level beside the existing regexes, not inside
the class.

- [ ] **Step 5: Implement both on GitLab**

In `host_providers/gitlab.py`, add to `GitLabProvider`. Note the **greedy owner** —
GitLab groups nest, so everything before the last segment is the owner, matching
how the existing `_GITLAB_BLOB_RE` handles it:

```python
_GITLAB_ORIGIN_RE = re.compile(
    r"^https://gitlab\.com/(?P<owner>.+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


    def tree_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://gitlab.com/{owner}/{repo}/-/tree/{ref}/{path}"

    def parse_origin(self, url: str) -> tuple[str, str] | None:
        m = _GITLAB_ORIGIN_RE.match(url.strip())
        return (m.group("owner"), m.group("repo")) if m else None
```

- [ ] **Step 6: Write the resolver**

Create `packages/haywire-core/src/haywire/core/marketstall/locate.py`:

```python
"""Turn a marketstall row's coordinates into a URL.

A row says *which repo* (``origin``), *which commit* (``install_spec``), and
*which file* (``docs_path``/``examples_path``/``tests_path``). It deliberately
stores no URLs: the ref would then live in four places that could disagree about
which commit was published, and raw-versus-rendered would be frozen at publish
time instead of chosen by the caller. This module is the one place those three
coordinates become a URL.

Resolution happens on the *reader's* machine, so a self-hosted host registered in
the reader's config resolves even when the publisher had never heard of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from urllib.parse import urlparse

from haywire.core.marketstall.host_providers import resolve_host

if TYPE_CHECKING:
    from haywire.core.marketstall.types import Haybale


def _ref_from_install_spec(install_spec: str) -> str | None:
    """The tag glued into a git+URL, or None. Single source of the commit."""
    spec = install_spec.strip()
    if " @ " in spec:
        spec = spec.split(" @ ", 1)[1].strip()
    spec = spec.removeprefix("git+")
    spec = spec.split("#", 1)[0].strip()
    _, _, tag = spec.rpartition("@")
    return tag.strip() or None if "@" in spec else None


def resolve_row_path(
    row: "Haybale",
    path: str,
    *,
    form: Literal["raw", "blob", "tree"],
) -> str | None:
    """Resolve *path* against *row*'s origin and ref.

    ``form`` picks the shape: ``"raw"`` to fetch bytes, ``"blob"`` to link a file
    in a browser, ``"tree"`` to link a directory.

    Returns None — never a guess — when the host is unrecognised, the row lacks
    ``origin`` or a ref, or *path* is empty. A wrong URL is worse than no link:
    the previous implementation guessed ``main``/``master`` and 404'd silently.
    """
    if not path or not row.origin or not row.install_spec:
        return None

    hostname = urlparse(row.origin).hostname
    if not hostname:
        return None
    provider = resolve_host(hostname)
    if provider is None:
        return None

    parsed = provider.parse_origin(row.origin)
    if parsed is None:
        return None
    owner, repo = parsed

    ref = _ref_from_install_spec(row.install_spec)
    if not ref:
        return None

    builder = {
        "raw": provider.raw_url,
        "blob": provider.blob_url,
        "tree": provider.tree_url,
    }[form]
    return builder(owner, repo, ref, path.lstrip("/"))


def link_form(path: str) -> Literal["blob", "tree"]:
    """Which browser form *path* wants: a trailing slash means a directory."""
    return "tree" if path.endswith("/") else "blob"
```

- [ ] **Step 7: Run the resolver test**

Run: `uv run pytest tests/marketstall/test_locate.py -v`

Expected: all PASS.

- [ ] **Step 8: Switch the producer to relative paths**

In `packages/haywire-core/src/haywire/core/publishing/marketstall.py`, replace the
`docs_url` construction (lines ~118-127) and the whole `_folder_url` helper
(lines ~133-149) with path derivation. Delete `_folder_url` — the `.haywire`-file
scan goes with it.

```python
    # Paths are relative to the git root and resolved by the consumer against
    # `origin` at `install_spec`'s ref — see haywire.core.marketstall.locate.
    # Trailing slash marks a directory.
    docs_path = ""
    if git_root and module_dir:
        docs_path = f"{module_dir.relative_to(git_root)}/"

    def _declared_path(declared: str) -> str:
        """Prefix an author-declared, library-relative path with the lib's own
        path from the git root. Empty when undeclared."""
        if not declared or not git_root:
            return ""
        rel = lib_dir.relative_to(git_root)
        joined = f"{rel}/{declared.lstrip('/')}"
        return joined
```

Then in the `Haybale(...)` construction, replace the three `*_url=` arguments:

```python
        origin=https_url if remote_url else "",
        docs_path=docs_path,
        examples_path=_declared_path(decorator_examples_path),
        tests_path=_declared_path(decorator_tests_path),
```

`decorator_examples_path` / `decorator_tests_path` come from the decorator. Until
the AST reader lands (migration step 9, a later plan), read them with the existing
quote-agnostic helper:

```python
from haywire.core.library.decorator_io import _get_decorator_str_field

init_file = module_dir / "__init__.py" if module_dir else None
content = init_file.read_text() if init_file and init_file.exists() else ""
decorator_examples_path = _get_decorator_str_field(content, "examples_path")
decorator_tests_path = _get_decorator_str_field(content, "tests_path")
```

If `_get_decorator_str_field` does not exist, add it to `decorator_io.py` mirroring
`_get_decorator_list_field`:

```python
def _get_decorator_str_field(content: str, field: str) -> str:
    """Read a quoted string field from the decorator source. '' if absent."""
    match = re.search(rf"[ \t]+{re.escape(field)}=['\"]([^'\"]*)['\"]", content)
    return match.group(1) if match else ""
```

Also rename `source_url=` → `origin=` in the same construction if Task 4 left it.

- [ ] **Step 9: Rewire the three consumers**

**`library_overview_editor.py`** — delete `_clickable_doc_url` entirely and
rewrite `collect_overview_links`:

```python
def collect_overview_links(pkg) -> list[tuple[str, str]]:
    """The (label, href) links shown in the library overview header.

    Examples are surfaced for humans; tests_path is deliberately NOT surfaced
    (framework-maintainer metadata only).
    """
    if pkg is None:
        return []
    links: list[tuple[str, str]] = []
    if pkg.origin:
        links.append(("Source", pkg.origin))
    for label, path in (("Docs", pkg.docs_path), ("Examples", pkg.examples_path)):
        if not path:
            continue
        href = resolve_row_path(pkg, path, form=link_form(path))
        if href:
            links.append((label, href))
    return links
```

with `from haywire.core.marketstall.locate import link_form, resolve_row_path`
at the top.

**`marketplace_state.py`** — in `fetch_overview`, replace the explicit-`docs_url`
branch and delete `_github_raw_base` plus the `main`/`master` guessing loop:

```python
        # ── 1. Resolve docs_path against the row's origin + ref ──────────────
        if pkg.docs_path:
            local = Path(pkg.docs_path)
            if local.is_dir():
                for candidate in (local / "OVERVIEW.md", local / "QUICKREF.md"):
                    if candidate.exists():
                        return candidate.read_text()
            elif local.is_file():
                return local.read_text()
            else:
                base = resolve_row_path(pkg, pkg.docs_path, form="raw")
                if base:
                    if base.endswith(".md"):
                        candidates = [base]
                    else:
                        stem = base.rstrip("/")
                        candidates = [f"{stem}/OVERVIEW.md", f"{stem}/QUICKREF.md"]
                    content = await asyncio.to_thread(_first_reachable, candidates)
                    if content:
                        return content
```

Keep the PyPI `long_description` fallback that follows. The removed heuristic
branch guessed a branch name; `resolve_row_path` uses the real ref or returns
None.

**`catalog_tools.py:178`** — replace the `pkg.docs_url` join:

```python
                if pkg.name == library and pkg.docs_path:
                    url = resolve_row_path(pkg, f"{pkg.docs_path.rstrip('/')}/{rel}", form="raw")
```

and skip the fetch when `url` is None.

- [ ] **Step 10: Update the producer and refresh tests**

```bash
grep -rn "docs_url\|examples_url\|tests_url\|source_url" --include="*.py" tests/
```

Update each to the new field names and to paths rather than URLs. Tests asserting
a generated absolute URL now assert a relative path plus a `resolve_row_path`
result.

- [ ] **Step 11: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/locate.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/locate.log
grep -E "passed|failed" /tmp/locate.log | tail -1
```

Expected: `exit=0`, no FAILED lines. This is where Task 4's deferred breakage must
be gone.

Watch for `assert Foo is Foo`-style failures — per
`.insights/feedback_barn_module_reload_test_trap.md`, tests importing barn classes
at module top-level go stale after `importlib.reload`. If one appears, the fix is
`importlib.import_module` + `patch.object`, not a change to this task's code.

- [ ] **Step 12: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [ ] **Step 13: Commit Tasks 4 and 5 together**

```bash
git add -A
git commit -m "refactor(library)!: LibraryMetadata base; rows carry coordinates

The library detail view renders from a marketstall row when one exists and from
the loaded identity otherwise (heaps, and libraries whose source was
unsubscribed, have no row). Sharing a base makes that one code path instead of
a per-field branch, and makes name parity structural rather than a test.

Rows now store coordinates instead of URLs: origin says which repo,
install_spec which commit, and docs_path/examples_path/tests_path which file,
relative to the git root. Consumers assemble URLs through HostProvider, which
gains tree_url() and parse_origin(). The ref therefore lives in exactly one
place and no two fields can contradict each other about which commit was
published; raw-vs-rendered becomes the caller's choice; and a self-hosted host
resolves against the reader's config rather than the publisher's.

Deletes _clickable_doc_url, _github_raw_base and _folder_url — three places
that each re-encoded the same host rules, one of which guessed main/master and
404'd when wrong. Also drops the .haywire-file scan that silently published
nothing for an examples folder holding anything else.

BREAKING CHANGE: marketstall rows drop six field names in favour of the base's:
'dependencies' -> 'linked_libraries' (stops colliding with [project]
dependencies), 'author' -> 'authors' (now a list), 'source_url' -> 'origin',
and 'docs_url'/'examples_url'/'tests_url' -> 'docs_path'/'examples_path'/
'tests_path', which now hold repo-relative paths rather than absolute URLs. No
parse aliases: a feed written before this loses those values, and feeds are
regenerated on every publish. The same 'dependencies' rename applies to the
decorator.

ADR 0024."
```

---

## Self-Review

**Spec coverage.** This plan implements migration steps **1, 2, 3, 4 and 5** —
the metadata shape and the coordinate-based row, which is the structural half of
the consolidation. It does **not** reach the consolidation's full goal on its own.

Steps 6–10 are deferred to follow-up plans, sequenced in "Out of scope" above as
**7 → 9 → 6 → 8 → 10**. Note that is not the consolidation doc's numbering: three
of those steps need `examples_path`/`tests_path`/`os` to be decorator kwargs,
which happens in step 7, so 7 must come first regardless of its number.

After this plan, a library's metadata is still authored in both places for the
duplicated fields (`version`, `description`, `author`, `tags`) — **step 7 is what
closes the drift** the consolidation exists to remove. This plan makes that
possible; it does not do it.

**Deviation from the design doc, flagged.** The consolidation doc spreads the
`Haybale` renames and the path/resolution change across its steps 5 and 6, after
the base class. This plan folds them together, because the base forces the issue:
the moment `Haybale` extends `LibraryMetadata` it *has* `linked_libraries`,
`authors`, and the three `*_path` fields, so leaving the old spellings declared
ships a class carrying both — the duplication this ADR exists to remove.

An earlier draft resolved that by renaming the three URL fields in Task 4 while
leaving them holding absolute URLs, with a docstring explaining the interval. That
was wrong twice over: a field named `docs_path` documented as repo-relative and
holding `https://raw.githubusercontent.com/...` misleads the next reader, and a
docstring apologising for a field's contents is a smell. Task 5 now lands the
producer, the resolver, and the consumers together, so `*_path` means what it says
from the commit it first appears in.

**Tasks 4 and 5 share one commit.** Task 4 removes `Haybale.docs_url` and friends;
nothing populates `*_path` until Task 5. Task 4 therefore ends *red* by design —
its Step 10 pins exactly which failures are expected (`AttributeError` on those
three attributes, from four named call sites) and says any other failure is a real
regression. This is the one place the plan departs from "every task ends green",
and it is deliberate: the alternative is a commit whose field names lie.

**Type consistency.** `reload_action` is defined in Task 3 (on `LibraryIdentity`)
and moves to the base in Task 4, where both subclasses inherit it — Task 4's test
asserts it on both. `linked_libraries` is `list[str]` of module names everywhere.
`on_reload` is `str` from Task 3 onward. `resolve_row_path(row, path, *, form)`
and `link_form(path)` are introduced in Task 5 Step 6 and used with those exact
signatures in Step 9.

**Three risks worth naming.**

1. Task 4 Step 4 moves `LibraryReloadAction` to a new module. `LibraryIdentity`
   has 84 construction sites and the enum is imported from `identity.py` in
   several places; the re-export keeps those working, but
   `from haywire.core.library.identity import _RELOAD_ACTION_RANK` (private, so
   unlikely) would break. The full-suite run is the check.
2. `HostProvider` is a `Protocol`, so adding `tree_url`/`parse_origin` silently
   un-satisfies any external implementation. Only `GitHubProvider` and
   `GitLabProvider` exist in-tree, and both are updated in Task 5.
3. Task 5 Step 8 reads `examples_path`/`tests_path` from the decorator with a
   regex helper because the AST reader arrives in a later plan (migration step 9).
   The helper is quote-agnostic, so it does not reintroduce Task 1's bug, but it
   *is* the third regex reader in the tree and should be deleted when the AST
   reader lands.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-08-library-metadata-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

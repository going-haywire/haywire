---
name: selection-toolbar-provider-explicit-forwarding
description: Handoff — replace SelectionToolbarProvider's getattr-based _delegate/_delegate_result with explicit one-line forwarding methods, make menu_provider a required constructor arg, and close a test-coverage gap the getattr indirection was hiding
metadata:
  type: project
  status: open
---

# Replace `_delegate`/`_delegate_result` with explicit forwarding

Identified 2026-09-17 while reviewing `SelectionToolbarProvider`
(`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection_toolbar.py`).
Not a bug — the code works — but the indirection has a real cost and an
8-of-13 test gap it was hiding. Scoped small enough to do in one sitting.

## The shape of it

13 of `SelectionActions`' 15 verbs (`surfaces/selection.py:24`) reach
`SelectionToolbarProvider` only to be re-thrown at
`SessionContextMenuProvider`, which does the actual work. Today that goes
through two helpers (lines 317–340):

```python
def _delegate(self, verb: str, *args: object) -> None:
    if self._menu_provider is None:
        logger.warning(...)
        return
    getattr(self._menu_provider, verb)(*args)

def _delegate_result(self, verb: str, *args: object) -> object:
    if self._menu_provider is None:
        logger.warning(...)
        return None
    return getattr(self._menu_provider, verb)(*args)
```

called from 13 one-line public methods, e.g. `set_selection_detail`
(line 311): `self._delegate("set_selection_detail", detail)`.

## What it costs

`getattr(self._menu_provider, verb)(*args)` is not a call expression the
tools can see. Confirmed by grep and by `codegraph_explore`: neither finds
`SelectionToolbarProvider` as a caller of
`SessionContextMenuProvider.set_selection_detail` (or any of the other 12) —
only the string literal shows up. Concretely:

- An IDE "find references" on any of the 13 methods on
  `SessionContextMenuProvider` misses this call site entirely.
- A rename-symbol refactor on any of those 13 method names will not touch
  the `self._delegate("old_name", ...)` string — it fails at runtime, not at
  refactor time, and only if the renamed verb is exercised.

## The coverage gap this was hiding

`tests/graph_editor/test_selection_toolbar_provider.py`'s
`test_missing_verbs_delegate_to_the_menu_provider` (line 192) parametrizes
only 5 of the 13 delegated verbs — `paste_at_click`, `redraw_selection`,
`revalidate_selection`, `reset_selection`, `dissolve_reroute`. The other 8
(`collapse_to_group`, `expand_group`, `enter_group`,
`set_selection_collapsed`, `selection_is_collapsed`,
`toggle_selection_collapsed`, `set_selection_detail`,
`clear_selection_detail_overrides`) are untested at the delegation level —
nothing pins that the verb string matches the method name or that args land
in the right order. That's exactly the class of typo explicit one-line
methods make easy to introduce and easy to catch; the generic parametrize
was never extended to cover them.

## Why `menu_provider` can become required, not `Optional`

`_menu_provider: Optional["SessionContextMenuProvider"]` is `Optional` for
exactly one reason: `tests/graph_editor/test_selection_toolbar_provider.py`'s
`_provider()` helper (line 19) defaults `menu_provider=None` so most tests
can build a `SelectionToolbarProvider` without also building a
`SessionContextMenuProvider`.

The single production call site,
`graph_canvas_manager.py:98-109`, never omits it — it constructs
`context_menu_provider` immediately above and passes it straight in. There is
no real code path where `_menu_provider` is absent.

Making it a required constructor arg removes the None-branch from all 13
forwarding methods at once (no guard, no log, nothing to duplicate 13 times)
and makes the type finally describe the one shape the class is ever built
with.

## The change

1. In `selection_toolbar.py`:
   - `menu_provider: "SessionContextMenuProvider"` (drop `Optional`, drop the
     `= None` default) in `__init__`, and `self._menu_provider = menu_provider`
     unconditionally (no `Optional[...]` on the attribute either).
   - Delete `_delegate` and `_delegate_result` (lines 317–340).
   - Replace each of the 13 call sites with a direct call, e.g.:
     ```python
     def set_selection_detail(self, detail: str) -> None:
         self._menu_provider.set_selection_detail(detail)

     def selection_is_collapsed(self) -> bool:
         return self._menu_provider.selection_is_collapsed()
     ```
   - The class docstring's "Host contract" paragraph (lines 68–77) and the
     "SelectionActions Protocol implementation" comment (lines 242–246)
     reference delegation as a design fact, not the `_delegate` helper by
     name — no change needed there, they stay true.

2. In `tests/graph_editor/test_selection_toolbar_provider.py`:
   - `_provider()` (line 19): drop the `menu_provider=None` default; build a
     `MagicMock()` internally when the caller doesn't supply one, and return
     it alongside `prov`/`registry` so callers that care can assert against
     it. Every existing call site (`_provider(monkeypatch)`,
     `_provider(monkeypatch, menu_provider=menu_provider)`) keeps working
     unchanged.
   - Delete `test_delegation_without_a_menu_provider_is_a_no_op` (line 211) —
     its premise (menu provider absent) is no longer constructible.
   - Extend `test_missing_verbs_delegate_to_the_menu_provider`'s
     parametrize list (line 192) with the 8 missing verbs:
     `("collapse_to_group", ())`, `("expand_group", ("n1",))`,
     `("enter_group", ("n1",))`, `("set_selection_collapsed", (True,))`,
     `("set_selection_detail", ("compact",))`,
     `("clear_selection_detail_overrides", ())`.
   - Add a second parametrized test for the two query verbs
     (`selection_is_collapsed`, `toggle_selection_collapsed`), asserting both
     that the call reaches the menu provider AND that its return value comes
     back through — `_delegate_result` forwarded returns too, and a plain
     `self._menu_provider.foo()` return-statement needs the same pin:
     ```python
     @pytest.mark.parametrize("verb", ["selection_is_collapsed", "toggle_selection_collapsed"])
     def test_query_verbs_return_the_menu_providers_answer(monkeypatch, verb):
         menu_provider = MagicMock()
         getattr(menu_provider, verb).return_value = True
         prov, _ = _provider(monkeypatch, menu_provider=menu_provider)
         assert getattr(prov, verb)() is True
     ```
   - `test_provider_satisfies_selection_actions` (line 180) and
     `test_copy_and_delete_are_emitted_directly` (line 218) are unaffected —
     neither touches `_menu_provider`.

## Where to start

- `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection_toolbar.py:80-97` (`__init__`), `248-340` (the 13 forwarding methods + the two helpers to delete)
- `tests/graph_editor/test_selection_toolbar_provider.py:19-35` (`_provider` helper), `192-215` (delegation tests)
- `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py:98-109` — confirm this is still the only construction site before relying on "never actually None"

## One thing to check on the way in

`tests/ui/graph_canvas/test_surface_protocols.py:97`
(`test_selection_actions_declares_the_batch_and_card_verbs`) and `:134`
(`test_both_hosts_of_selection_menu_satisfy_its_protocol`) check the
`SelectionActions` Protocol structurally (`isinstance`/attribute presence),
not how a verb is implemented — they should pass unchanged and don't need
editing. If either fails after this refactor, something else broke.

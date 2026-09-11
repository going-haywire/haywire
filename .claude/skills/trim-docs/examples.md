# Calibration examples

Rewrites of docstrings and comments from this codebase. Match their shape and length. The `curate-trim-examples` skill maintains this file.

Each entry names one category in its heading, has a `Source` line naming the file, symbol, and the commit the code was read at, and a `Displayed` line saying whether the app shows the docstring to users (Markdown) or not (reST).

## User-facing class: `OPTIONAL`

Source: packages/haywire-core/src/haywire/barn/builtin/types/optional.py::OPTIONAL at 7fdb0915
Displayed: yes (Markdown)
Teaches: rewriting in the user's vocabulary, and stating a surprising behavior as a plain warning instead of justifying it. A registered component's docstring reaches users as Markdown (generated docs, the Component Docs editor, `describe_component`), so code blocks are indented, not introduced with `::`.

```python
class OPTIONAL(WrapperType[T]):
    """A setting that can be left unset.

    Use this for library parameters where you want the library's own default
    unless the user picks a value. When the setting is unset, you simply don't
    pass that parameter.

    Declare it by wrapping the value type:

        class NmsSettings(NodeSettings):
            eta   = setting[OPTIONAL[FLOAT]](None, min=0.0, max=1.0, label="Eta")
            top_k = setting[OPTIONAL[INT]](None, min=1, max=1000, label="Top K")

    The first argument is the default, and `None` means unset. `min` and `max`
    limit the widget only: unset is always allowed, so you don't need a
    placeholder like `-1`, and a value from a connected pin isn't checked
    against them, so check the range in your worker if it matters.

    In your worker, the setting reads as its value or `None`. Pass along only
    what's set:

        kwargs = {k: v for k, v in {"eta": self.nms.eta, "top_k": self.nms.top_k}.items()
                  if v is not None}

    An unset setting is saved and restored like any other value.

    When exposed as a pin, an `OPTIONAL[INT]` setting is an ordinary `INT` pin
    and connects anywhere an `INT` does. While it's unset:

    - a connected `OPTIONAL` input receives `None`.
    - a connected regular `INT` input receives nothing and keeps its previous
      value, so it may hold a stale value until this setting is set again.
    """
```

Removed: absence versus "whether a tier has a view", why promotion needs no adapter, how `accepts_absence()` resolves edges, the `int(None)` failure.
Kept: how to declare it, what the worker reads, save and load, what connected pins receive, including the stale-value case, and that `min`/`max` reach only the widget (`descriptor.py` stamps them into `widget_config`; an edge writes the shared cell through `Pipe.pull` and `DataPort.set_value` with no range check).

## User-facing class: `ErrorNodeSkin`

Source: barn/haybale-studio/haybale_studio/skins/error_skin.py::ErrorNodeSkin at 7fdb0915
Displayed: yes (Markdown)
Teaches: a component docstring reaches users as Markdown (the Component Docs editor, and `describe_component`), so it stays plain user-facing text — no reST roles, no internals.

```python
class ErrorNodeSkin(NodeSkin):
    """The card a node falls back to when its own skin raises or can't be resolved.

    Inlets and outlets are drawn in two columns, pinless configs full width
    beneath, with the node's diagnostics badge and a footer counting each side.

    Node collapse is ignored: every visible port is drawn, so a broken node
    never hides the ports you opened it for.
    """
```

Removed: why the fallback renders through its own body instead of subclassing, and the argument for showing everything.
Kept: what the card is for, what it shows, and the one behavior that differs from other skins.

## Protocol or abstract base: `PortActions`

Source: barn/haybale-graph-editor/haybale_graph_editor/surfaces/pin.py::PortActions at 7fdb0915
Displayed: no (reST)
Teaches: mapping each member to what the user sees, without arguing for the design.

```python
@runtime_checkable
class PortActions(Protocol):
    """Actions in a pin's right-click menu. All of them apply only to promoted pins.

    - ``demote_setting``: "Detach from setting".
    - ``set_port_show_widget``: "Show widget".
    - ``reset_setting``, ``clear_setting``: the same actions as the setting's
      row menu in the Properties panel, so an edit made in the pin's widget
      can be undone on the pin.
    """
```

Removed: the argument for why the value actions exist in two places.
Kept: what each member backs in the UI.

## Overridable method: `DataField.accepts_absence`

Source: packages/haywire-core/src/haywire/core/types/fields.py::DataField.accepts_absence at 7fdb0915
Displayed: no (reST)
Teaches: a timing guarantee looks like rationale but is contract, because an overrider must respect it.

```python
def accepts_absence(self) -> bool:
    """Return whether this field can hold ``None`` as an intentional "unset" value.

    Decides what an edge delivers when its source is unset: ``None`` if the
    sink returns True, otherwise nothing, and the sink keeps its value.
    Called once when the edge is built, so the result must not depend on
    the field's current value.
    """
    return False
```

Removed: "storage capability, NOT type compatibility", "only ever the same question by accident", and the comparison with `get_stored_type()`.
Kept: what the result decides, and the call-timing guarantee.

## Public method: `required_access`

Source: packages/haywire-core/src/haywire/core/access/tier.py::required_access at e0a4c4ee
Displayed: no (reST)
Teaches: a fallback is stated as an outcome; the reason each fallback is the right one, and the list of callers that share it, go.

```python
def required_access(cls: type) -> AccessTier:
    """Return the tier a principal needs before ``cls`` may be shown or called.

    Returns ``VIEW`` when ``cls`` has no ``class_identity``, when the identity
    has no ``access`` field (node, skin, widget and theme identities have none;
    see ADR 0027), or, with a warning logged, when ``access`` isn't a valid
    tier name.
    """
```

Removed: "one definition for all three gated surfaces" and how each enforces, the "all deliberate" bullets explaining hot-reload hiccups, ungated identities, and typo safety.
Kept: the three inputs that yield `VIEW`, and the warning, because a caller debugging an unexpectedly visible panel needs exactly those.

## Public method: `NodeData.add`

Source: packages/haywire-core/src/haywire/core/node/data.py::NodeData.add at e0a4c4ee
Displayed: no (reST)
Teaches: sections that restate the signature go, and every remaining claim is checked against the code — here the old docstring promised an input the code rejects.

```python
def add(self, spec: "dict[Any, Any] | PortSpec") -> DataPort:
    """Add an inlet or outlet from a port spec and return the built port.

    The port joins the enclosing ``group()`` and ``section()`` blocks, if
    any, and is ordered after the ports added before it. Inside ``rejig()``,
    re-adding a port ID the block flagged replaces that port and keeps its
    edges (see ``DataPort.adopt_state_from``); any other existing ID raises
    ``ValueError``::

        self.add(FLOAT.as_inlet("value"))
    """
```

Removed: `Args:` and `Returns:` that repeat the signature, "no race condition!", the bullet list narrating each assignment, and two claims the code doesn't honor: that a built `DataPort` is accepted (`DataPort.from_spec` reads `spec["kwargs"]`) and an example calling `group("advanced")` with a bare name (`group()` takes a `GROUP` spec).
Kept: what the port joins, the one case where a duplicate ID is allowed, and the exception otherwise.

## Rationale moved to a line comment: `reset_setting`

Source: barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py::SessionContextMenuProvider.reset_setting at 7fdb0915
Displayed: no (reST)
Teaches: a reason that matters only to maintainers moves from the docstring to the line it explains.

```python
def reset_setting(self, port_id: str) -> None:
    """Reset the setting behind ``port_id`` to its declared default.

    Same as "Reset to default" in the setting's row menu in the Properties
    panel.
    """
    # Through the bag, not the port: writing the port alone doesn't update
    # the bag's record of which settings the user has set.
    ...
```

Removed from the docstring: the routing explanation, now a two-line comment.
Kept: what it does and which UI action it matches.

## Private helper: `_widget_model_for`

Source: packages/haywire-core/src/haywire/ui/widget/factory.py::_widget_model_for at 7fdb0915
Displayed: no (reST)
Teaches: describing the effect a caller sees instead of the internal bookkeeping that causes it.

```python
def _widget_model_for(port: DataPort) -> Any:
    """Return the model a port's widget binds to.

    For a promoted port, a model that writes through the owning setting, so
    edits on the pin are saved and can be reset like edits in the Properties
    panel. Otherwise, or if no setting matches the port, the port itself.
    """
```

Removed: "one cell, two views", the `_to_dict`/`_set_keys` internals, why the check isn't in `DataPort.set_value`, the comparison with `demote_setting`.
Kept: both return cases and the effect on saving and Reset.

## Long comment trimmed to a constraint: `_metadata_to_port_kwargs`

Source: packages/haywire-core/src/haywire/core/node/promotion.py::_metadata_to_port_kwargs at 7fdb0915
Displayed: no (reST)
Teaches: keeping a pointer to where a behavior lives instead of the argument for it.

```python
def _metadata_to_port_kwargs(descriptor: "setting") -> dict:
    """Build ``IType.as_inlet``/``as_outlet`` kwargs from a setting descriptor.

    Wrapper types are replaced by their element type (``OPTIONAL[INT]`` gives
    an ``INT`` port). ``label`` falls back to the attribute name, and
    ``widget_key``/``widget_config`` are included only when set.
    """
    # Wrapper settings promote as their element type (OPTIONAL[INT] -> INT pin).
    # Unset values still cross OPTIONAL -> OPTIONAL edges; see DataField.accepts_absence.
    type_cls = descriptor._type
    ...
    # Skip an empty widget_config; it would replace the IType's default config.
    widget_config = getattr(descriptor, "widget_config", None)
    if widget_config:
        ...
```

Removed: the underscore-attribute translation, the `ui/skin/base.py` path, the widget-fallback reasoning, and the ADR 0017 adapter-matrix argument.
Kept: what the result contains, and two short comments at the lines they explain.

## Comment with history: `_build_adapter_chain`

Source: packages/haywire-core/src/haywire/core/edge/edge_wrapper.py::EdgeWrapper._build_adapter_chain at 7fdb0915
Displayed: no (reST)
Teaches: deleting what used to be true and keeping only what is true now.

```python
def _build_adapter_chain(self) -> bool:
    """Build the adapter chain for this edge. Call only after ``_formal_validation`` succeeds."""
    ...
    # Compare wire types; they differ from the declared types for
    # PooledField and wrapper fields (OPTIONAL[INT] sends INT).
    sink_type = inlet_port.stored_type
    source_type = outlet_port.stored_type
```

Removed: what the two ends used to ask, and which type used to hide the asymmetry.
Kept: which types are compared and where they differ.

## Comment with history: `_MENU_ROW_DISABLED_STYLE`

Source: packages/haywire-core/src/haywire/ui/elements/elements.py::_MENU_ROW_DISABLED_STYLE at e0a4c4ee
Displayed: no (reST)
Teaches: a `#:` attribute comment is a comment, so it gets four lines at most; the paragraph on how the old style worked goes, and "NOT the same constant as X" becomes one line saying how X differs.

```python
#: Pointer events stay on so a ``tooltip=`` still opens on a disabled row; the
#: hover rule in ``app/shell.py`` skips ``.hw-disabled`` itself. ``cursor`` is
#: reset because ``.hw-menu-row`` sets ``pointer``. ``flyout._DISABLED_STYLE``
#: differs: its ``pointer-events: none`` is what keeps an empty submenu shut.
_MENU_ROW_DISABLED_STYLE = "opacity: 0.4; cursor: default"
```

Removed: how `pointer-events: none` used to suppress the hover background, that nothing else depended on it, and the `@click.self` overlay detail.
Kept: why each declaration is present, and the one sibling constant a maintainer might wrongly unify with this one.

## Describes another component: `INTField`

Source: packages/haywire-core/src/haywire/barn/builtin/types/specs.py::INTField at 70f5cfa8
Displayed: no (reST)
Teaches: why another class builds on this one is that class's story; this docstring keeps only what this field does.

```python
class INTField(PrimitiveField):
    """Field for ``INT`` values.

    Every write goes through ``int()``: ``3.7`` stores ``3`` and ``None``
    raises ``TypeError``.
    """
```

Removed: the comparison with `setting[FLOAT]`, why `OPTIONAL[INT]` derives its field from this one, and how the wrapper's absence branch bypasses the coercion.
Kept: the coercion and its two visible outcomes.

## Module docstring: `publishing/manifest/deps.py`

Source: packages/haywire-core/src/haywire/core/publishing/manifest/deps.py::module at 70f5cfa8
Displayed: no (reST)
Teaches: a module docstring says what the module offers and how it differs from its sibling; how the readers used to work goes.

```python
"""Read a library's label and ``linked_libraries`` from its ``haybale.toml``.

Both readers return a fallback (the given label, or an empty list) when the
file is missing or malformed, so a report or scaffold that calls them still
runs. The strict reader that refuses such a library when it is loaded is
:mod:`haywire.core.library.haybale_toml`.
"""
```

Removed: that both functions used to regex `__init__.py`, and the argument for parsing TOML instead.
Kept: what the readers return on failure, and where the strict reader lives.

## Leave alone: `flyout_category`

Source: packages/haywire-core/src/haywire/ui/elements/flyout.py::flyout_category at 7fdb0915
Displayed: no (reST)
Teaches: over the length guide is not a reason to cut — every line here tells a caller something they must act on, so the docstring stays as it is.

```python
def flyout_category(label, siblings, tooltip="", *, dense=True):
    """Render one hover-opening category flyout and yield its child sibling group.

    Creates a ``ui.menu_item`` anchor (with a right-arrow affordance) whose nested
    ``ui.menu`` flyout opens on hover, registering it into ``siblings`` and wiring
    the sibling-close behaviour. Inside the ``with`` block the flyout is the active
    NiceGUI slot, so callers render its contents (leaf ``ui.menu_item``s,
    separators) directly; subcategories recurse by calling ``flyout_category``
    again, passing the *yielded* child sibling group as their ``siblings``.

    ``tooltip``, when non-empty, is attached to the *anchor row* (not the flyout
    body) so hovering the category shows its help text — the caller can't reach the
    internal anchor, so the primitive wires it.

    ``dense`` sets the anchor's Quasar density, and must match the density of the
    *sibling* items it lines up with — a ``dense`` q-item has smaller padding, so
    an anchor that disagrees with the plain ``menu_item``s above it sits visibly
    shorter than the rest of the menu. It defaults True for ``NodeMenuBuilder``,
    whose own leaves are dense; a settings row's menu, whose Reset/Promote items
    are not, passes ``dense=False``. The caller cannot fix this after the fact:
    the anchor is internal and only the child sibling group is yielded.
    """
```

Removed: nothing. Seventeen prose lines against a limit of ten, yet each paragraph is a caller decision: how to nest, where the tooltip lands, and which `dense` value to pass.
Kept: all of it.

## Scan false positive: `_package_root`

Source: packages/haywire-studio/src/haywire_studio/packaging/docs/generate.py::_package_root at 7fdb0915
Displayed: no (reST)
Teaches: the scan's caps flag fires on `OVERVIEW` and `QUICKREF`, which are generated filenames (`OVERVIEW.md`, `QUICKREF.md`), not emphasis — so there is nothing to change.

```python
def _package_root(module_dir: Path) -> Path | None:
    """The library's package root (dir holding pyproject.toml + README), or None.

    Package layout: the parent of the module dir. Flat layout: the module dir
    itself. Framework-owned libraries baked inside another package (e.g.
    ``haywire.barn.builtin`` inside haywire-core) have no own package root and
    return None — they get in-wheel docs (OVERVIEW/QUICKREF/docs) but no README.
    """
```

Removed: nothing. The helper is at its five-line limit and every line is an outcome the caller reads.
Kept: both layouts and the `None` case.

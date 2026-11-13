# Docstring cleanup notes

Design reasoning removed from docstrings during `/trim-docs`, kept here because
it is architectural and no ADR in `docs/adr/` covers it. One entry per topic.

## Observable Store: why the listener seam

`packages/haywire-core/src/haywire/core/farmhand/activity.py` — module, and
`ActivityTracker._notify`

`ActivityTracker` is the second implementation of the shape `ErrorLedger`
established: an ambient `get_`/`set_` accessor surviving hot-reload, a zero-arg
listener list fired on every state change, an app-side bridge turning those
fires into a cross-session signal, and a payload-free signal whose subscribers
re-read the store.

The store notifies listeners instead of calling
`get_signal_dispatcher().broadcast(...)` itself, which it could. Three reasons:
`SignalDispatcher.broadcast` dispatches synchronously into the single-threaded
SignalBus, so a self-broadcasting store would have to capture an event loop at
startup and hold it as state — safe for this tracker, which is touched only
from the loop, but not for `ErrorLedger`, whose `.log()` fires from watchdog
and timer threads; a bare `ActivityTracker()` stays inert and directly
testable; and which signal a state change means is the application's policy,
which a headless embedding or a second host may answer differently.

The tracker deliberately omits `ErrorLedger`'s triage half — no `seen` flag, no
per-record sequence, no second "triage changed" signal. An error is a task
someone must acknowledge; a finished tool call is a fact.

## Graph filestem is derived from the path, never read back from the file

`packages/haywire-core/src/haywire/core/graph/base.py` — `BaseGraph.__init__`,
`save_to_file`, `load_from_file`, `load_from_dict`

A file's stem is a fact about the file, so a copy serialized inside it goes
stale the moment the file is renamed or copied. `save_to_file` and
`load_from_file` therefore both stamp `filestem` from the real path, and
`load_from_dict` ignores the `filestem` key it finds in the data. The
constructor argument is only a seed for a graph that has no file yet, which is
the one moment the seed is the right thing to show.

## GraphMetadata is a settings bag, and the framework-written fields stay out of it

`packages/haywire-core/src/haywire/core/graph/metadata.py` — module, and
`GraphMetadata`

Label, description, author and version are a settings bag rather than four
plain attributes so that the settings framework owns their editing,
serialization and change propagation, the way it already does for
`GraphProperties` (ADR 0022). `filestem`, `created_at` and `modified_at` are
deliberately not fields on the bag: they have no setter, and a generic bag
renderer draws every field it holds as editable. Unlike `graph.props` the bag
declares no `shadow()` fields and no node-side mirrors, which is why its
restore order relative to the nodes is unconstrained.
## Node settings keys: why `_setting_key` carries no node identity

`packages/haywire-core/src/haywire/core/node/decorator.py` —
`_wire_settings_schemas`

A node bag's field key is `'<accessor>.<field>'` and never gains the node's
`registry_key` as a prefix. Two reasons were recorded in the docstring: the
accessor alone already separates same-named fields across the bags on one node,
and — the load-bearing one — the `setting` descriptors of an inherited bag
(every node's `props`) are one shared set of objects, so a node-specific prefix
would leave whichever node was decorated first stamped on every other node's
fields.

The same sharing is why the stamp is applied on every `@node` rather than only
when the key is unset: the value depends solely on the accessor, so re-stamping
a shared descriptor writes the identical string, while a per-node bag subclass
still gets keyed off its own accessor.

## Suggested version specifiers are floors, never ceilings

`packages/haywire-core/src/haywire/core/library/dep_detect.py` —
`_format_specifier`

Detection emits `<dist>>=<installed version>` for framework, registered-library
and third-party dists alike. A compatible-release specifier was rejected for
the framework and lockstep dists: `~=X.Y.Z` implies a `==X.Y.*` ceiling, and
lockstep packages have no independent compatibility boundary to express, so a
generated ceiling would exclude the next minor without anyone deciding it. A
tool-suggested upper bound is also the kind nobody revisits, so an author who
wants one writes it by hand; the project scaffolder emits `>=` for the same
reason.

## Dependency edits name their entries; nothing rewrites the whole array

`packages/haywire-core/src/haywire/core/library/dep_edit.py` — module

The module offers no "replace the dependency list" operation, which is what
keeps the framework requirement owned by the single step that writes it: with
only entry-level verbs available, a step resolving unrelated drift cannot
overwrite the `haywire-core` floor as a side effect. The same property protects
entries carrying extras, environment markers or direct references, none of
which import detection can reproduce. `set_dependency` changes a named entry,
`add_dependencies` only appends what is missing, `remove_dependencies` deletes
by distribution name.

## A library that cannot name itself does not load

`packages/haywire-core/src/haywire/core/library/haybale_toml.py` —
`HaybaleTomlError`, `read_haybale_toml`

The decoration-time reader raises instead of defaulting to empty fields. An
empty default would hand the library an empty `linked_libraries`, and the
resulting failure — a subscriber holding a stale class after a hot reload —
surfaces much later and somewhere unrelated. Raising is affordable because the
registry wraps each library's load, so one broken library is visibly absent
while the studio still starts.

The reactive subsystem (Reactive[T] + @reads) is Vue 3's reactivity / Solid.js's signals. Path-level reads (Session.active_graph.edges) are Vue's reactive-proxy idea. Before either of those, Knockout.js (2010) and S.js (2013) had the same model; before that, dependency-tracking spreadsheets back to VisiCalc. You don't need to learn anything new here — it's the standard fine-grained reactive pattern.

Critically, this isn't foreign to Haywire. The engine already uses reactive props at the node layer (shadow(), watch(), the descriptor system). Extending that pattern up to the UI layer is consistency with the engine, not a new framework idea bolted on. That's a provenance point worth being honest about: A+ leans on a primitive your codebase already commits to, just deployed at a different level.

Typed action APIs as protocols is hexagonal architecture / ports-and-adapters (Alistair Cockburn, ~2005). The protocol is the port; GraphCanvasManager is the adapter; tests substitute fakes against the port. Python's typing.Protocol (PEP 544, 2019) is what makes it ergonomic.

Host[C] / Child[C] with class-keyed routing is generic-typed DI (Spring, Angular, ASP.NET) plus the React/Vue/SwiftUI component-tree mental model. Stringly-typed routing as an anti-pattern is well-known (C2 wiki, Coding Horror, ~2004); typed dispatch is the standard fix.

Focus as a class hierarchy is sealed-classes-as-discriminated-union — ML's algebraic data types (1973), Scala/Kotlin/Rust enums, TypeScript discriminated unions. Using __subclasses__() as discovery is Pythonic but the underlying idea is "type hierarchy is the registry."

State placement by lifetime is general scope-of-shared-mutable-state hygiene — Elm's model, Redux's principles, the Rust borrow checker, all the way back to "minimize scope" being a principle since structured programming. The specific rule ("longest reader owns it") is mine, but it's just an articulation of common practice.

DisplayPanel vs Panel[C] is Command/Query Separation (Meyer, ~1988) plus the old React presentational-vs-container split (Dan Abramov, 2015). The split exists in many UI frameworks; I named it for this context.

Layout carrying rendering position, not EditorContext is SwiftUI/Compose's modifier model: a view doesn't know where it's drawn; the parent decides. HTML+CSS works the same way (an element doesn't know its position: rule). This is one place I made a deliberate composition choice — separating "what to render" from "where" is the move that makes popup-vs-pane disappear from the panel's mental model.

What I actually invented (or chose) for this codebase:

Gesture state on Session (§6.2). Reframing popup-internal state as session-scoped gesture state is a design call I made by following the placement rule. It's not lifted from anywhere — it's what falls out when you reject "popup-internal" as a valid state lifetime and ask where the state actually belongs.
The −11 / +4 count is rhetorical. It's an Antoine de Saint-Exupéry / Rich Hickey ("Simple Made Easy") framing — small composable cores beat large flat APIs.
The specific four primitives (Session, Host[C], Child[C], EditorContext) is the minimal set I could find that covers the cases in your code. A different starting set would produce a different A+. I tested it against the dual-editor panel, the canvas popup, the "add a new editor" case, and tests — but I didn't test it against, say, modal dialogs or the haystack editor. There may be a primitive missing for cases I didn't walk through.
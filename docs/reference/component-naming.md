---
status: accepted
doc_template: reference
scope: The naming scheme for node, data type and widget classes and their labels, and which of its rules `haywire docs` checks
see-also:
  - glossary.md
  - ../components/nodes/node-canon.md
  - ../components/datatypes/datatype-canon.md
  - ../components/widgets/widget-canon.md
  - ../haybale/haybale-canon.md
---

# Component naming

Each component has one name, and the name ends with what the thing is. A node
class is its label in CapWords plus `Node`, a widget class ends in `Widget`,
and a registered data type is `SCREAMING_SNAKE`.

A class name is part of the component's registry key
(`<library>:<kind>:<ClassName>`), and saved graphs store that key. Choose the
name before you publish, because renaming the class later breaks every saved
graph that holds the old key (see [node canon](../components/nodes/node-canon.md)).

## N — nodes

| Rule | Form | Conforming examples |
|---|---|---|
| N1 | The class is the label in CapWords plus `Node`. Either one can change, but they change together | `LoadImageNode` / "Load Image" |
| N2 | A one-shot operation (DATA or CONTROL node) puts the verb first | `SplitPathNode`, `SendFrameNode`, `UpscaleImageNode` |
| N3 | A stateful device or source is an agent noun | `AudioMixerNode`, `RecorderNode`, `TrackerNode`, `WebCameraNode` |
| N4 | An inspector is `<Thing>Info` | `ImageInfoNode`, `MetadataInfoNode` |
| N5 | An EVENT node is `<Trigger>Event` | `TickEventNode`, `AudioEventNode`, `ImageEventNode` |
| N6 | An emitter that feeds event nodes is `<What>Emit` | `TickEmitNode`, `ReceiveFrameEmitNode` |
| N7 | An abstract base is `Base<X>Node` | `BaseEstimatorNode` |
| N8 | No implementation detail (`Numpy`) or library name, unless it tells two palette entries apart | `LoadSpandrelModelNode` keeps "Spandrel" |
| N9 | In haybale-testing: `<X>ProbeNode`, benchmarks `Bench<X>Node`, never a `Test` prefix. pytest collects `Test*` classes, and test modules import these nodes | `FoldProbeNode`, `BenchSinkNode` |
| N10 | A node template (`@node(template=True)`, hidden, cloned and never placed; see *Node template* in the [glossary](glossary.md)) is `<Kind>NodeTemplate`, its label the template kind | `DataNodeTemplate` / "Data Node" |

## T — data types

| Rule | Form | Conforming examples |
|---|---|---|
| T1 | Every registered type is `SCREAMING_SNAKE`, generics included. CapWords plus `Type` is for unregistered base classes only | `OPTIONAL[T]`, `DRAIN[T]`; bases `PrimitiveType`, `CompoundType`, `WrapperType` |
| T2 | A compound name puts the head noun last | `FILE_PATH`, `DETECTION_RESULT`, `IMAGE_MODEL`, `RGB_IMAGE` |
| T3 | A family root is the bare noun, with no `_BASE` | `IMAGE`, `PATH`, `CARRIER` |
| T4 | Wire-role types follow T2: `<NAME>_CALLBACK`, `<NAME>_EXEC`. The bare `CALLBACK` and `EXEC` are core's | `AUDIO_CALLBACK`, `AUDIO_EXEC` |
| T5 | Short code names are fine; the label spells them out | `INT` / "Integer", `VEC3F` |

## W — widgets

| Rule | Form | Conforming examples |
|---|---|---|
| W1 | A generic control is `<Control>Widget`, in the words users see on the matching widget node (Toggle, Menu, Slider) | `SliderWidget`, `MenuWidget`, `ToggleWidget` |
| W2 | An editor tied to one type is `<Type in CapWords>Widget` | `PathWidget`, `ColorWidget`, `ModelRefWidget` |
| W3 | No vague qualifiers ("Simple") and no abbreviations the type doesn't use | `MatrixWidget`, `LabelWidget`, `VectorWidget` |
| W4 | The constant in `widget_keys.py` is the class name in SCREAMING_SNAKE | `PATH_WIDGET` |

## X — all kinds

| Rule | |
|---|---|
| X1 | An acronym in CapWords is written as a word: `Midi`, `Osc`, `Rgb` (`SendMidiNode`, `ImageToRgbAdapter`). Brand names keep their spelling: `ComfyUI`, `OakD` |
| X2 | Labels are Title Case and never contain the word "Node": "Load Image", "RGB Image", "Error" |
| X3 | A module file is renamed only together with its class, and follows the majority in its folder (`nodes/merge_channels.py`, `widgets/label_widget.py`). No file-only renames |

Adapters already follow `<From>To<To>Adapter` and are not covered here.

## Accepted exceptions

| Component | Breaks | Why it stays |
|---|---|---|
| `haywire-core:node:GraphNode`, label "Group" | N1 | It is the Graph-node base that `MacroNode` extends. Splitting out a `GroupNode` is an architecture change, not a rename |

The check still reports an accepted exception.

## What `haywire docs` checks

The coverage report at the end of every `haywire docs` run (see
[haybale canon](../haybale/haybale-canon.md), §10) also lists naming lines for
the rules a program can check. They are reports only and never fail a run.
Libraries in `[tool.haywire.docs].coverage_exempt` still get their naming lines.
Node templates (N10) are not checked.

| Rule | Line reported when |
|---|---|
| N1 | A node class doesn't end in `Node`, or, ignoring case, spaces and punctuation, isn't its label plus `Node` |
| N7 | A public node class of the library that a registered node inherits from, and that is not itself registered, isn't `Base<X>Node`. Reported once per library |
| N9 | A node class starts with `Test` |
| W1 | A widget class doesn't end in `Widget` |
| T1 | A registered type's class name isn't `SCREAMING_SNAKE` |

N1 compares letters only, so it lets `MidiSendNode` / "MIDI Send" pass; X1 and
the word-order rules (N2–N6, T2–T4) are for review. A line reads:

```text
haywire-core:node:GraphNode: naming: N1 class `GraphNode` is not its label 'Group' + `Node`
```

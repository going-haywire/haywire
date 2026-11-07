# Carrier types and Metadata nodes: design

Settled by design conversation on 2026-11-06. Reverses non-goal 8 of
[the spandrel spec](2026-10-30-spandrel-haybale-design.md) and replaces its S9 item.

| Plan | Repo | Status |
|---|---|---|
| [A: carrier types and Metadata nodes](2026-11-06-carrier-metadata.md) | haywire-repo | built 2026-11-06, uncommitted; live check owed |
| [B: visiongraph on image types](2026-11-06-visiongraph-on-image-types.md) | haybale-visiongraph | built 2026-11-06 on feat/image-types, uncommitted; needs A released, live check owed |

## 1. Why

Visiongraph has its own frame types (`RGB_FRAME` actually holds BGR), and a frame's timestamp
and number live inside the type. Moving it to `IMAGE_RGB` and `IMAGE_GRAY` needs a place for
that data. A type ladder (`VIDEO_RGB`, `CAMERA_RGB`) was rejected as too many types. Instead,
any value can carry named fields, and what a node needs stays visible as ordinary pins.

## 2. Types and values

```text
Pins (type)                        Data (value)
CARRIER  (core, hidden)            CarrierValue  (core)
├── IMAGE (haybale-image)          ├── ImageValue
│   ├── IMAGE_GRAY                 ├── DepthValue
│   ├── IMAGE_RGB                  └── BundleValue (core)
│   └── IMAGE_RGBA
├── DEPTH (haybale-image)
└── BUNDLE (core)
```

- A pin of type `CARRIER` accepts every child through the existing child-to-parent passthrough
  (`factory.py:230`) and refuses everything else. No adapter targets `CARRIER`.
- `DEPTH` and `BUNDLE` are siblings of `IMAGE`, so they cannot reach an `IMAGE` inlet.
- `CARRIER` derives from `PrimitiveType[CarrierValue]`. `PrimitiveType.__init_subclass__` only
  recognises a direct `PrimitiveType[...]` base, so `IMAGE`, `DEPTH` and `BUNDLE` set
  `element_type_cls` in their class bodies.
- `IMAGE`'s registry key does not depend on its base class, so saved graphs still load.

## 3. Fields

- **A field** is a key and a value on a `CarrierValue`, recorded with the type it was stamped as.
- **Keys** match `[a-zA-Z0-9_]+` and are case-sensitive. Libraries prefix theirs by convention
  (`camera_timestamp`); nothing enforces it.
- **Values** are any object, treated as immutable and never saved. Stamping returns a new
  carrier; the upstream value and other branches never see it.
- **ICC and EXIF stay in `ImageMetadata`.** They describe the file and are used by Save Image.
  The Metadata node can neither read nor change them. Metadata Info lists them read-only.
- Save Image does not write fields to the file. `codecs.py` needs no change.

### What keeps fields

| Operation | ICC / EXIF | Fields |
|---|---|---|
| A node makes new pixels and calls `derive` | kept | dropped |
| A bare `from_array` / `from_tensor` | none | none |
| Layout adapters (`convert_layout`) | kept | kept |
| A node passes them on deliberately (`with_fields`) | n/a | kept |

Upscale Image and Inpaint pass fields on (changed 2026-11-07), accepting that a field holding a pixel position goes stale. To keep a field across a node that drops it, read it before and stamp it after.

## 4. Nodes

### Metadata

Holds two settings of type `FIELD_LIST`, **Stamp** and **Read**, neither promotable. Each entry
is a key and a type, added and removed in a widget. A change rebuilds the pins with `rejig` from
`_subscribe_field`, the existing settings-first pattern (ADR 0013).

| Pin | Id | Notes |
|---|---|---|
| Carrier in | `carrier_inlet` | Plain `CARRIER` inlet. Never retypes |
| Carrier out | `carrier_outlet` | Retypes to the connected source's type |
| Stamp field | `<key>_in` | Unwired, it stamps its own widget's value |
| Read field | `<key>_out` | Plain `T` outlet, shows no widget |

- Field pins have origin `DECLARED`: the list owns them, so the pin menu must not remove them.
- The fixed pins cannot clash with field pins, because they do not end in `_in` or `_out`.
- Renaming means remove and add, which drops wires. Re-adding a key relinks its old wires.
- Removed fields leave their edges in the graph in an error state, and those edges are saved,
  as with the pin menu's `remove_port`. Undo relinks them.
- The carrier inlet is plain rather than `ADD[CARRIER]`: swapping RGB for DEPTH then needs no
  slot to reopen. This simplifies what the design conversation proposed.
- Stamps apply before reads, so one node can stamp and read the same key.

### Read outcomes

| Situation | Outlet writes | Node state |
|---|---|---|
| Key present, recorded type equals or derives from the pin's | the value | fine |
| Key absent | the pin type's default | fine |
| Key present, type mismatch | the pin type's default | error, after all pins are written |

Error text: `Field 't' holds FLOAT, this pin reads STRING`.

**Why absent does not write `None`:** tested 2026-11-06, an `OPTIONAL[INT]` outlet writing `None`
leaves a plain `INT` inlet holding the last value (wrote 6, then `None`: the inlet reads 6). A
frame missing its timestamp would silently show the previous one. Writing the default is
deterministic. This replaces the earlier decision that an absent read gives `None`.

### Others

- **Library nodes** subclass `MetadataNodeBase` and declare fixed fields as class attributes.
- **New Bundle** outputs an empty `BUNDLE`, the start of a chain of stamps.
- **Metadata Info** lists what a carrier holds: each field's key, type and value summary, plus
  the lines from `CarrierValue.describe()` (`icc: 3144 bytes`).

## 5. Depth

One `DEPTH` type with a `DepthValue`: `uint16` millimetres, `H×W`, immutable, in `haybale-image`.
No adapter touches it, so colourizing stays an explicit node.

## 6. Type picker

`TypeRegistry.list_value_type_keys()` returns visible types on a `DEPENDENT` wire. `FOLD`,
`PROGRESS` and `CHOICES` get `hidden=True`, as does `CARRIER`. Hidden types also leave Farmhand's
default catalog listing; `include_hidden` still shows them. Arrays are not offered yet; entries
store a type recipe so they can be added without a format change.

## 7. Bundle use

A camera delivering three images can stamp `color`, `depth` and `ir` on a `BUNDLE`, with no new
machinery. The costs: a wrong key shows only at run time, and contents are invisible on the wire.
So nodes with fixed outputs keep typed outlets, and bundles serve content that varies.

## 8. To land with the code

### ADR 0075: fields travel on a carrier, and pins show what a node needs

Status accepted. See also ADR 0013, ADR 0033, ADR 0034, ADR 0043.

**Context.** Visiongraph's frame types bundle pixels with a timestamp and frame number. Extra
data on a value is invisible on the wire, while a type per combination multiplies types.

**Decision.** Any type deriving from `CARRIER` carries named fields. A Metadata node stamps and
reads them through pins declared in its settings, by key and type. A manipulating node drops
fields; a layout conversion keeps them. ICC and EXIF stay apart because they describe the file.
An absent read writes the pin type's default, because `None` leaves the consumer's last value.

**Alternatives.** *`VIDEO_` and `CAMERA_` types:* too many types, and the ladder has no end.
*Wire-grown field pins with labels as keys:* a pin took its type from the consumer, so a stored
float could reach a `STRING` inlet unconverted, and typos failed silently. *One bag for ICC and
fields:* `derive` would special-case keys, and a field called `icc` would replace the profile.

**Consequences.** Wrong keys and types surface at run time. `Metadata Info` is the way to see
what a value holds. Renaming a field drops its wires.

### Glossary

| Term | Definition | Avoid |
|---|---|---|
| **Carrier** | A value that can hold fields; its type derives from `CARRIER` (`IMAGE`, `DEPTH`, `BUNDLE`) | Metadata bag |
| **Field (carrier)** | A key and value stamped on a carrier, recorded with its type; dropped by manipulating nodes, never saved | Tag, metadata entry |
| **Stamp** | To return a new carrier with a field set | Attach |
| **Bundle** | A carrier with no content of its own, used to carry several values together | Frame (one execution pass), META |
| **Depth value** | A `uint16` millimetre buffer, the value of `DEPTH` | Depth frame |
| **Image metadata** | Add to the entry: distinct from a carrier's fields | |

### Insight

`.insights/project_optional_outlet_keeps_stale_value.md`, plus one line in `CLAUDE.md`: writing
`None` to an `OPTIONAL[T]` outlet does not reach a plain `T` inlet, which keeps its last value.
A node must write a value to clear a downstream reading.

### Spandrel spec

Non-goal 8 and the S9 row point here.

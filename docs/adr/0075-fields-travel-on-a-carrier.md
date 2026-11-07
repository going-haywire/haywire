---
name: fields-travel-on-a-carrier
description: Any type deriving from CARRIER holds named fields, stamped and read through pins a Metadata node declares by key and type; manipulating nodes drop fields, and an absent read writes the pin type's default
status: accepted
see-also: ADR-0013, ADR-0033, ADR-0034, ADR-0043
level: architectural
---

# Fields travel on a carrier, and pins show what a node needs

**Context.** Visiongraph's frame types bundle pixels with a timestamp and a frame number. Extra data on a value is invisible on the wire, while a type per combination (`VIDEO_RGB`, `CAMERA_RGB`) multiplies types and has no natural end.

**Decision.** Any type deriving from `CARRIER` holds named fields, on a value deriving from `CarrierValue`. A Metadata node stamps and reads them through pins declared in two settings of type `FIELD_LIST`, by key and type; a change rebuilds the pins with `rejig`. Keys are `[a-zA-Z0-9_]+`, and pin ids are `<key>_in` and `<key>_out`.

- `derive` copies only `ImageMetadata`, so a node making new pixels drops fields unless it passes them on with `with_fields`. Only the node knows whether a field still holds: Upscale keeps them, so a timestamp stays true and a pixel position goes stale. A layout conversion keeps them.
- ICC and EXIF stay in `ImageMetadata`: they describe the file and are used by Save Image.
- **Write Fields** on Save Image stores fields in a PNG, as JSON in one uncompressed `iTXt` chunk before the pixels; Load Image restores them. It is off by default, since fields then travel with a shared file.
- A field can be stored when its type is not declared `NEVER` and its value converts to JSON, stays within 1 MB and reads back as the same JSON. The declaration alone is not enough (a `LIST` can hold anything), and neither is JSON (an image's `to_dict` succeeds and holds no pixels).
- Writing is all or nothing: a field that cannot be stored fails the save, naming every such field, and no file appears. The setting is an explicit request, so a missing field would be a silent failure. Reading stays lenient: a field whose type is not installed is left out with a warning, so a missing library cannot make an image unopenable. A file cannot ask for a type declared `NEVER`.
- An absent read writes the pin type's default. Writing `None` to an `OPTIONAL[T]` outlet leaves a plain `T` inlet on its last value, so a frame missing a field would silently show the previous frame's.
- A stamped type the pin cannot read writes the default and reports an error on the node, after every pin is written.
- The carrier inlet is a plain `CARRIER` pin, which accepts every derived type; only the outlet retypes, so swapping an image for a depth map needs no slot to reopen.

**Alternatives.** *`VIDEO_` and `CAMERA_` types:* too many types. *Wire-grown field pins with labels as keys:* a pin took its type from its consumer, so a stored float could reach a `STRING` inlet unconverted, and a typo failed silently. *One bag for ICC and fields:* `derive` would special-case keys, and a field called `icc` would replace the profile. *An absent read writes `None`:* see above.

**Consequences.** Wrong keys and types surface at run time, not at connection, and a consumer cannot tell an absent field from a real default; Metadata Info shows what a value holds. Renaming a field drops its wires, and re-adding the key relinks them. A removed field's edges stay in the graph in an error state and are saved, like those of any removed pin. To keep a field across a node that drops it, read it before and stamp it after.

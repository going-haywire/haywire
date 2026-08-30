# StringToChoicesAdapter

`haywire-core:adapter:StringToChoicesAdapter` · kind: adapter

String into a choices slot

## Details

- **converts_from**: `haywire-core:type:STRING`
- **converts_to**: `haywire-core:type:CHOICES`
- **priority**: `0`

## Notes

STRING -> CHOICES needs an explicit adapter: CHOICES is the descendant,
so (per adapter-canon.md) an ancestor-to-descendant conversion is never a
free passthrough — not every string is a valid choice. The reverse
direction (CHOICES -> STRING) needs no adapter at all: CHOICES(STRING)
already gets a free passthrough via AdapterFactory's
issubclass(source_type, sink_type) check.

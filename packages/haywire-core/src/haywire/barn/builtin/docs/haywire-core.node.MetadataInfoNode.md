# Metadata Info

`haywire-core:node:MetadataInfoNode` · kind: node

Lists the fields an image or bundle carries

## Ports

| id | direction | type | description |
|---|---|---|---|
| `carrier` | inlet | `haywire-core:type:CARRIER` | The value to list |
| `text` | outlet | `haywire-core:type:STRING` | What the value carries, one line each |
| `count` | outlet | `haywire-core:type:INT` | How many fields the value carries |

## Notes

Lists what an image, depth map or bundle carries.

- `Text`: one line per field with its key, type and value, followed by what the
  value holds besides fields, such as the size of an image's ICC profile.
- `Count`: how many fields it carries.

# Metadata

`haywire-core:node:MetadataNode` · kind: node

Stamps fields on an image or bundle, and reads them back

## Ports

| id | direction | type | description |
|---|---|---|---|
| `carrier_inlet` | inlet | `haywire-core:type:CARRIER` | The value to stamp and read |
| `carrier_outlet` | outlet | `haywire-core:type:CARRIER` | The value with its stamps |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `stamp` | metadata_fields | `FIELD_LIST(entries=())` | Fields to set, each with an inlet |
| `read` | metadata_fields | `FIELD_LIST(entries=())` | Fields to get, each with an outlet |

## Notes

Stamps named fields on an image, depth map or bundle, and reads them back.

List fields under **Stamp** and **Read** in the Properties panel, each with a key
and a type. A field does nothing until it is listed.

- **Stamp** adds an inlet `<key>`. Wired, it stamps the incoming value; unwired, it
  stamps the value typed into it.
- **Read** adds an outlet `<key>`. A field that is not there gives the type's default,
  such as 0 or an empty text.
- **Carrier** passes the value on with its stamps. The input itself is not changed.

Stamps apply before reads. Reading a field stamped as another type gives the default
and reports an error on the node. So does a missing field on a type with no default,
such as a model, since what the pin feeds would keep its last value. Renaming a field
means removing and adding it, which drops its wires.

A node that makes new pixels drops the fields unless its help says it keeps them; to
keep one anyway, read it before that node and stamp it after. Changing an image's
channels keeps them. Fields are not saved, either with the graph or in image files.

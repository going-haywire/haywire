# Adapters

`haybale-graph-editor:panel:EdgeAdapterEditMenuPanel` · kind: panel

## Details

- **surface**: `edge-edit`
- **order**: `10`

## Notes

One row per adapter in the edge's chain, each opening its source.

Reads ``Edge.chain_adapter_keys`` — the same ordered list the "Adapter
Chain" properties panel displays — rather than walking
``first_adapter._chain`` itself.

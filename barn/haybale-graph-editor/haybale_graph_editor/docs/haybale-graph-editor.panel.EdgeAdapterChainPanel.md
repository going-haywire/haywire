# Adapter Chain

`haybale-graph-editor:panel:EdgeAdapterChainPanel` · kind: panel

## Details

- **surface**: `edge`
- **order**: `45`

## Notes

List the adapters converting the source value to the sink type, in order.

Reads ``Edge.chain_adapter_keys`` — the registry keys ``_build_adapter_chain``
already resolved and ordered — rather than walking ``first_adapter._chain``
itself, so this shows exactly what the last successful build produced.

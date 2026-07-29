# List components

`studio:farmhand:list_components` · kind: farmhand

ALWAYS pass at least one of kind=/library=/search= — omitting all three returns every installed component (100+) and is slow and almost never what you want. Component catalog, filterable and searchable.
Start with count_only=true to see totals per library/kind before listing rows — the cheapest way to survey scope.
kind: one of adapter, editor, farmhand, node, panel, setting, skin, state, theme, type, widget
library: exact library id (see studio_list_libraries)
search: substring match against label/description/search_tags (same algorithm as the node-menu search)
count_only: return counts grouped by library/kind instead of rows
include_hidden: include internal components (e.g. reroute/error nodes), excluded by default
include_system: include synthetic libraries (dunder ids like '__system__'), excluded by default

## Details

- **input_schema**: `{'type': 'object', 'properties': {'library': {'type': 'string'}, 'kind': {'type': 'string', 'enum': ['adapter', 'editor', 'farmhand', 'node', 'panel', 'setting', 'skin', 'state', 'theme', 'type', 'widget']}, 'search': {'type': 'string'}, 'include_hidden': {'type': 'boolean', 'default': False}, 'include_system': {'type': 'boolean', 'default': False}, 'count_only': {'type': 'boolean', 'default': False}, 'limit': {'type': 'integer', 'default': 100}, 'offset': {'type': 'integer', 'default': 0}}, 'required': []}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`

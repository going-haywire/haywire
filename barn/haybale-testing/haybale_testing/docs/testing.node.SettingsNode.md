# Settings Test Node

`testing:node:SettingsNode` · kind: node

Test the Settings for debugging

## Ports

| id | direction | type | description |
|---|---|---|---|
| settings | outlet | builtin:type:STRING | Text data |

## Settings

| name | bag | default | description |
|---|---|---|---|
| example_string | example | 'default string' | An example string setting |
| example_int | example | 3 | An example integer setting |
| example_float | example | 5 | A float setting with explicit type_ override |
| example_bool | example | False | An example boolean setting |
| example_choices | example | 'fast' | An example choices setting |
| example_color | example | '#00ff00' | An example color setting |
| example_vec2i | example | [4, 8] | A 2-component integer vector |
| example_vec3f | example | [1.0, 2.0, 3.0] | A 3-component float vector |
| example_vec4f | example | [0.0, 0.0, 0.0, 1.0] | A 4-component float vector (e.g. RGBA or homogeneous coords) |
| persistent_value | example | 1.0 | Normal stored setting |
| intensity | example | None | Library-wide default intensity used by test nodes |
| count_mirror | example | None | Library-wide integer default used by test nodes |
| label_mirror | example | None | Library-wide string default used by test nodes |
| enabled | example | None | Library-wide boolean default used by test nodes |
| mode | example | None | Library-wide mode choice used by test nodes |
| tint | example | None | Library-wide color default used by test nodes |
| offset | example | None | Library-wide 2D integer offset used by test nodes |
| position | example | None | Library-wide 3D float position used by test nodes |
| intensity_ro | example | None | Library-wide default intensity used by test nodes |
| count_ro | example | None | Library-wide integer default used by test nodes |
| label_ro | example | None | Library-wide string default used by test nodes |
| enabled_ro | example | None | Library-wide boolean default used by test nodes |
| mode_ro | example | None | Library-wide mode choice used by test nodes |
| tint_ro | example | None | Library-wide color default used by test nodes |
| offset_ro | example | None | Library-wide 2D integer offset used by test nodes |
| position_ro | example | None | Library-wide 3D float position used by test nodes |
| validated_string | example | 'hello' | Must be non-empty |
| clamped_positive | example | 1.0 | Must be positive (validator rejects <= 0) |
| even_int | example | 4 | Must be an even integer |

## Notes

Node that exercises all setting() — suppress spurious delete test.

# Fill

`haybale-example:type:FILL` · kind: type

Solid colour or gradient background

## Details

- **flow_type**: `data`
- **default**: `{'kind': 'solid', 'angle': 135, 'stops': [{'color': '#1e1e1eff', 'at': 0}]}`
- **widget_key**: `haybale-example:widget:FillWidget`
- **color**: `#f7b0ff`

## Notes

A node card's background: a solid colour, or a linear/radial gradient.

``stops`` is a list of ``{'color': '#rrggbbaa', 'at': 0..100}``. ``kind``
decides how many of them matter: ``solid`` reads only the first, the
gradients read all of them. Keeping the full list across a kind switch is
deliberate — flipping solid → linear → solid must not destroy the stops the
user already picked.

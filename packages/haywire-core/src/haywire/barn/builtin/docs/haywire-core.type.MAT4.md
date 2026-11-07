# Matrix 4x4

`haywire-core:type:MAT4` · kind: type

4x4 matrix: a 3D transform, a view or a projection

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'value': [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]}`
- **widget_key**: `haywire-core:widget:MatrixWidget`
- **color**: `#757575`

## Notes

A 4x4 matrix of floats, starting as the identity.

Rows come first: `m[row][col]`, as in numpy and OpenCV, so `np.array(m)` gives the
matrix. Data from OpenGL lists columns first and needs transposing.

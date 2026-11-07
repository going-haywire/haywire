# Matrix 3x3

`haywire-core:type:MAT3` · kind: type

3x3 matrix: a 2D transform, a homography, a camera matrix or a 3D rotation

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'value': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}`
- **widget_key**: `haywire-core:widget:MatrixWidget`
- **color**: `#757575`

## Notes

A 3x3 matrix of floats, starting as the identity.

Rows come first: `m[row][col]`, as in numpy and OpenCV, so `np.array(m)` gives the
matrix. Data from OpenGL lists columns first and needs transposing.

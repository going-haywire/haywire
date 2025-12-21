"""
Test compound type transformations.

This demonstrates how the adapter factory handles:
1. Scalar → Scalar transformations
2. ArrayType[X] → ArrayType[Y] transformations (same structure)
3. MapType[X] → ArrayType[Y] transformations (structural change)
"""

# Example usage (pseudocode):

# Case 1: Scalar transformation
# FLOAT → INT
# Factory finds: [FloatToIntAdapter]

# Case 2: Same compound structure
# ArrayType[FLOAT] → ArrayType[INT]
# Factory finds:
#   1. ArrayArrayAdapter (registered in core library)
#   2. Injects FloatToIntAdapter into it
# Result: [ArrayArrayAdapter(FloatToIntAdapter)]

# Case 3: Structural transformation
# MapType[FLOAT] → ArrayType[INT]
# Factory finds:
#   1. MapToArrayAdapter (registered structural adapter)
#   2. FloatToIntAdapter (element transformation)
#   3. Wraps both in StructuralAdapter (core system)
# Result: [StructuralAdapter(MapToArrayAdapter, FloatToIntAdapter)]

# The EdgeWrapper just calls:
# chain, error = adapter_factory.create_chain(
#     source_type=outlet_type,
#     target_type=inlet_type,
#     connection_uuid=edge_uuid
# )
#
# All compound type complexity is handled transparently!

"""
Core data definitions for the Haywire system.

This module exports the core data components including enums,
data field specifications, and factory functions for creating data fields.
"""

from haywire.core.data.enums import DataType, DataCategory, FlowType, CouplingType
from haywire.core.data.specs import DataFieldSpec, specs_factory

# --- Factory functions for creating DataFieldSpec instances ---
#
#  By default you would put the factory functions for creating DataFieldSpec instances here
# INT = specs_factory(
#         id='INT', 
#         label='Integer', 
#         description='Integer data type',
#         type=DataType.INT,
#         category=DataCategory.SCALAR,
#         widget='number',
#     )
#
# But for convenience reasons, the factor functions for core are located
# 
# -> haywire.core.data.__init__
#
# this way, third party libraries can reference them for their own adaptors.

__all__ = [
    # Enums
    "DataType",
    "DataCategory", 
    "FlowType",
    "CouplingType",
    # Specs
    "DataFieldSpec",
    "specs_factory",
]

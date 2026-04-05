"""
Test custom type: Simple test data structure.

This demonstrates a custom type from test_a library that can be used
by nodes in other libraries (like test_b).
"""

from dataclasses import dataclass, field, asdict
from typing import Any

from haywire.core.types.decorator import type
from haywire.core.types.base import BaseType
from haywire.ui import elements as hui


@type(
    registry_id="test_data",
    label="Test Data",
    description="Simple test data structure for cross-library testing",
    color="#FF5722",
    icon=hui.icon.type_database,
    default={"value": None},
    help_url="https://haywire.io/docs/types/test-data",
)
@dataclass
class TestData(BaseType):
    """
    A simple test data structure.

    Demonstrates a custom type that can be passed between nodes
    across different libraries.

    Attributes:
        value: Primary value (can be any type)
        label: Descriptive label for the data
        metadata: Optional metadata dictionary
    """

    value: Any = None
    label: str = "Test Data go"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """
        Serialize test data to dictionary format.

        Returns:
            Dictionary containing all data
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TestData":
        """
        Deserialize test data from dictionary format.

        Args:
            data: Dictionary containing test data

        Returns:
            New TestData instance
        """
        return cls(**data)

    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata to the test data.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata value.

        Args:
            key: Metadata key
            default: Default value if key not found

        Returns:
            Metadata value or default
        """
        return self.metadata.get(key, default)

    def __str__(self) -> str:
        """String representation of the test data."""
        return f"TestData('{self.label}', value={self.value}, metadata_keys={list(self.metadata.keys())})"

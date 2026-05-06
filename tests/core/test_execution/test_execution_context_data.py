"""Tests for ExecutionContext.data — class-keyed LibraryState access."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.state import LibraryState, LibraryStateContainer
from haywire.core.state.data_namespace import DataNamespace


class TestExecutionContextData:
    def test_data_field_default_none(self):
        """If no data namespace is provided, the field is None."""
        ctx = ExecutionContext(global_ctx={}, local_ctx={})
        assert ctx.data is None

    def test_data_field_can_be_set(self):
        class Pool(LibraryState):
            pass

        container = LibraryStateContainer()
        instance = Pool()
        container._instances_by_class[Pool] = instance

        ns = DataNamespace(container)
        ctx = ExecutionContext(global_ctx={}, local_ctx={}, data=ns)
        assert ctx.data is ns
        assert ctx.data[Pool] is instance

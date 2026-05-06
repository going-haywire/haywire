"""Tests verifying HaywireVM populates ExecutionContext.data from its container."""

from unittest.mock import MagicMock

from haywire.core.execution.vm import HaywireVM
from haywire.core.state import LibraryState, LibraryStateContainer
from haywire.core.state.data_namespace import DataNamespace


class TestVMLibraryStateWiring:
    def test_vm_without_container_creates_context_with_data_none(self):
        vm = HaywireVM()
        flow = MagicMock()
        flow.graph_ref.variables = {}

        ctx = vm._create_execution_context(flow=flow)
        assert ctx.data is None

    def test_vm_with_container_populates_data_namespace(self):
        class Pool(LibraryState):
            pass

        container = LibraryStateContainer()
        instance = Pool()
        container._instances_by_class[Pool] = instance

        vm = HaywireVM(library_state_container=container)
        flow = MagicMock()
        flow.graph_ref.variables = {}

        ctx = vm._create_execution_context(flow=flow)
        assert isinstance(ctx.data, DataNamespace)
        assert ctx.data[Pool] is instance

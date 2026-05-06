"""Tests verifying HaywireVM populates ExecutionContext.app_data from its container."""

from unittest.mock import MagicMock

from haywire.core.execution.vm import HaywireVM
from haywire.core.state import AppState, LibraryStateContainer
from haywire.core.state.data_namespace import AppDataNamespace


class TestVMLibraryStateWiring:
    def test_vm_without_container_creates_context_with_app_data_none(self):
        vm = HaywireVM()
        flow = MagicMock()
        flow.graph_ref.variables = {}

        ctx = vm._create_execution_context(flow=flow)
        assert ctx.app_data is None

    def test_vm_with_container_populates_app_data_namespace(self):
        class Pool(AppState):
            pass

        container = LibraryStateContainer()
        instance = Pool()
        container._app[Pool] = instance

        vm = HaywireVM(library_state_container=container)
        flow = MagicMock()
        flow.graph_ref.variables = {}

        ctx = vm._create_execution_context(flow=flow)
        assert isinstance(ctx.app_data, AppDataNamespace)
        assert ctx.app_data[Pool] is instance

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
        from haywire.core.state.identity import LibraryStateClassIdentity

        class Pool(AppState):
            pass

        Pool.class_identity = LibraryStateClassIdentity(
            class_name="Pool",
            module=__name__,
            registry_id="Pool",
            registry_key="test:state:Pool",
            label="Pool",
        )

        container = LibraryStateContainer()
        instance = Pool()
        container._app[Pool.class_identity.registry_key] = instance
        container._class_by_registry_key[Pool.class_identity.registry_key] = Pool

        vm = HaywireVM(library_state_container=container)
        flow = MagicMock()
        flow.graph_ref.variables = {}

        ctx = vm._create_execution_context(flow=flow)
        assert isinstance(ctx.app_data, AppDataNamespace)
        assert ctx.app_data[Pool] is instance

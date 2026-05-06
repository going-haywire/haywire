"""Tests for ExecutionContext.app_data — class-keyed AppState access."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.state import AppState, LibraryStateContainer
from haywire.core.state.data_namespace import AppDataNamespace


class TestExecutionContextData:
    def test_app_data_field_default_none(self):
        """If no app_data namespace is provided, the field is None."""
        ctx = ExecutionContext(global_ctx={}, local_ctx={})
        assert ctx.app_data is None

    def test_app_data_field_can_be_set(self):
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

        ns = AppDataNamespace(container)
        ctx = ExecutionContext(global_ctx={}, local_ctx={}, app_data=ns)
        assert ctx.app_data is ns
        assert ctx.app_data[Pool] is instance

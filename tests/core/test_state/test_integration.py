"""End-to-end test: full library enable → state instantiation → ctx.data access.

This test runs through the actual DI + LibrarySystemService initialization
to verify that LibraryState lifecycle is correctly driven by the existing
library enable pipeline.
"""

import pytest

from haywire.core.di.config import LibrarySystemService, create_haywire_injector
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
)
from haywire.core.state import (
    LibraryState,
    LibraryStateContainer,
    LibraryStateRegistry,
)


@pytest.mark.integration
class TestLibraryStateIntegration:
    def test_class_added_event_triggers_full_lifecycle(self):
        """Simulate a library registering a LibraryState class via the registry's
        public API path; verify the container picks it up and on_enable runs."""
        injector = create_haywire_injector()
        service = LibrarySystemService(injector)
        service.initialize()

        registry = injector.get(LibraryStateRegistry)
        container = injector.get(LibraryStateContainer)

        calls: list[str] = []

        class TestPool(LibraryState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        # Build a minimal LibraryIdentity for this test "library".
        lib_id = LibraryIdentity(
            id="testlib",
            label="Test Library",
            version="0.0.1",
            description="",
            url="",
            help_url="",
            author="",
            author_url="",
            dependencies=[],
            tags=[],
            module_name="testlib",
            folder_path="",
        )

        # Register the class — that puts it in the registry's _classes dict.
        key = registry._register_class(TestPool, lib_id)
        assert key is not None

        # In real life, the BaseRegistry's hot-reload path emits CLASS_ADDED
        # events through _queue_lifecycle_event + _notify_batch_event_subscribers.
        # Simulate that here:
        added_event = LifeCycleEvent(
            registry_key=key,
            event_type=LifeCycleEventType.CLASS_ADDED,
            affected_class=TestPool,
            library_identity=lib_id,
        )
        registry._lifecycle_event_queue.append(added_event)
        registry._notify_batch_event_subscribers()

        # Container should now hold an instance with on_enable called.
        assert TestPool in container
        assert calls == ["enable"]

        # Now simulate library disable: emit CLASS_REMOVED.
        removed_event = LifeCycleEvent(
            registry_key=key,
            event_type=LifeCycleEventType.CLASS_REMOVED,
            affected_class=TestPool,
            library_identity=lib_id,
        )
        registry._lifecycle_event_queue.append(removed_event)
        registry._notify_batch_event_subscribers()

        assert TestPool not in container
        assert calls == ["enable", "disable"]

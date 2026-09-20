"""The macro registry reaches the app through DI, not only through tests."""

import pytest

pytestmark = pytest.mark.integration


def test_the_library_system_provides_a_macro_registry(library_system):
    from haywire.core.macro.registry import MacroRegistry

    assert isinstance(library_system.get_macro_registry(), MacroRegistry)


def test_the_registry_is_a_singleton(library_system):
    assert library_system.get_macro_registry() is library_system.get_macro_registry()


def test_the_node_factory_is_built_over_it(library_system):
    """Discovery spans both registries only if the factory actually holds it."""
    factory = library_system.get_node_factory()

    assert factory.macro_registry is library_system.get_macro_registry()


def test_libraries_can_register_a_macros_folder(library_system):
    """add_folder_to_registry resolves MacroRegistry, which the scaffold relies on."""
    from haywire.core.macro.registry import MacroRegistry

    registries = library_system.get_library_registry()._class_registries

    assert registries.get(MacroRegistry) is library_system.get_macro_registry()

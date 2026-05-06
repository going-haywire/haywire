"""Tests verifying Interpreter forwards LibraryStateContainer to its VM."""

from haywire.core.execution.interpreter import Interpreter
from haywire.core.state import LibraryStateContainer


class TestInterpreterLibraryState:
    def test_interpreter_without_container_has_vm_with_no_container(self):
        interpreter = Interpreter()
        assert interpreter.vm._library_state_container is None

    def test_interpreter_forwards_container_to_vm(self):
        container = LibraryStateContainer()
        interpreter = Interpreter(library_state_container=container)
        assert interpreter.vm._library_state_container is container

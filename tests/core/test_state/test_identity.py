"""Unit tests for LibraryStateClassIdentity."""

from haywire.core.state.identity import LibraryStateClassIdentity


class TestLibraryStateClassIdentity:
    def test_carries_required_fields(self):
        ident = LibraryStateClassIdentity(
            registry_id="MidiPool",
            registry_key="midi:state:MidiPool",
            label="MidiPool",
            class_name="MidiPool",
            module="haybale_midi.state.midi_pool",
        )
        assert ident.registry_id == "MidiPool"
        assert ident.registry_key == "midi:state:MidiPool"
        assert ident.label == "MidiPool"
        assert ident.class_name == "MidiPool"
        assert ident.module == "haybale_midi.state.midi_pool"
        # Inherited defaults from BaseIdentity:
        assert ident.description == ""
        assert ident.deprecation_warning == ""

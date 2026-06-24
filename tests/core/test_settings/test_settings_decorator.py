"""@settings decorator stores deprecation_warning on SettingsClassIdentity."""

import pytest

from haywire.core.settings.decorator import settings, SettingsClassIdentity
from haywire.core.settings.schema import LibrarySettings


def test_deprecation_warning_stored_on_identity():
    @settings(namespace="test.ns", deprecation_warning="Use new_ns instead.")
    class OldSettings(LibrarySettings):
        pass

    assert OldSettings.class_identity.deprecation_warning == "Use new_ns instead."


def test_deprecation_warning_defaults_to_empty_string():
    @settings(namespace="test.ns2")
    class FineSettings(LibrarySettings):
        pass

    assert FineSettings.class_identity.deprecation_warning == ""

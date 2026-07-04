"""The self-mirror hack is gone (ADR 0016).

``_mirror_key`` means only "mirrors ANOTHER setting". Persistent fields on
FrameworkSettings/LibrarySettings no longer stamp ``_mirror_key`` to their own
``_setting_key`` — their machinery keys off ``_setting_key`` + the
registry-owned cell. ``is_cross_mirror`` collapses to ``bool(_mirror_key)``.
"""

from __future__ import annotations

from haywire.core.settings.descriptor import setting, shadow
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.schema import FrameworkSettings
from haywire.core.settings.node_settings import NodeSettings
from haywire.barn.builtin.types import FLOAT


class _NoMirrorSchema(FrameworkSettings, namespace="test.nomirror"):
    threshold = setting[FLOAT](1.5, label="Threshold")


KEY = "test.nomirror.threshold"


def test_persistent_field_has_no_mirror_key():
    desc = _NoMirrorSchema.__dict__["threshold"]
    assert desc._setting_key == KEY
    assert desc._mirror_key == ""
    assert desc.is_cross_mirror is False


def test_shadow_is_cross_mirror():
    class _Bag(NodeSettings):
        mirrored = shadow(_NoMirrorSchema.threshold)

    desc = _Bag.__dict__["mirrored"]
    assert desc._mirror_key == KEY
    assert desc.is_cross_mirror is True


def test_persistent_read_write_still_live_without_mirror_key():
    registry = SettingsRegistry()
    registry.register_schema(_NoMirrorSchema)
    bag = _NoMirrorSchema()

    assert bag.threshold == 1.5
    bag.threshold = 3.5  # persists via registry.set_global -> write-through
    assert bag.threshold == 3.5
    assert registry.cell_for(KEY).get_value() == 3.5

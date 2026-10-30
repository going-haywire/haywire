"""Volumes: named roots that graphs reference by ``(volume, relative)`` instead of absolute paths."""

from haywire.core.volumes.resolve import (
    VolumeError,
    VolumeEscapeError,
    VolumeStatus,
    VolumeUndefinedError,
    list_volumes,
    location_of,
    resolve,
)
from haywire.core.volumes.store import VolumeStore, get_volume_store, set_volume_store
from haywire.core.volumes.value import VolumePath
from haywire.core.volumes.volume import HomeVolume, ProjectVolume, Volume, all_volumes, volume_by_name

__all__ = [
    "HomeVolume",
    "ProjectVolume",
    "Volume",
    "VolumeError",
    "VolumeEscapeError",
    "VolumePath",
    "VolumeStatus",
    "VolumeUndefinedError",
    "VolumeStore",
    "all_volumes",
    "get_volume_store",
    "list_volumes",
    "location_of",
    "resolve",
    "set_volume_store",
    "volume_by_name",
]

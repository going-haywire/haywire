"""Surfaces declared by the studio library.

One file per surface, holding the surface and the Protocol it names in
``provides`` — a convention, not machinery.
"""

from haybale_studio.surfaces.file import FileActions, FileMenu

__all__ = ["FileActions", "FileMenu"]

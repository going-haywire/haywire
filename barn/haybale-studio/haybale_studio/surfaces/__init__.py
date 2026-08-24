"""Surfaces declared by the studio library.

One file per surface, holding the surface and the Protocol it names in
``provides`` — a convention, not machinery.
"""

from .file import FileActions, FileMenu

__all__ = ["FileActions", "FileMenu"]

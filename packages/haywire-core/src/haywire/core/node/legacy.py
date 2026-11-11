"""Marks carried by node data that an older graph file was upgraded from."""

from typing import Final

LEGACY_PORTS_KEY: Final = "legacy_ports"
"""Key in a node's data: true when its ports were saved by a file older than format v5."""

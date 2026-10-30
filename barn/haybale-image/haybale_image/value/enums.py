"""Enums describing an image's channels and their storage order."""

from enum import StrEnum


class Layout(StrEnum):
    """Which channels an image has, independent of how they are stored."""

    GRAY = "gray"
    RGB = "rgb"
    RGBA = "rgba"


class ChannelOrder(StrEnum):
    """Order of the colour channels in a buffer; alpha, when present, is always last."""

    RGB = "rgb"
    BGR = "bgr"

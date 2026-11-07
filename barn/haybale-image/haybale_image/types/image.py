"""IMAGE and its layout-fixed variants IMAGE_GRAY, IMAGE_RGB and IMAGE_RGBA."""

from typing import Any, ClassVar, cast

from haywire.barn.builtin.wires import DataWire
from haywire.barn.builtin.types import CARRIER
from haywire.core.types import PrimitiveField, StoreStrategy
from haywire.core.types import type as type_decorator

from haybale_image.value import ImageValue, Layout

_COLOR = "#3f8fd2"


def _empty_default(layout: Layout) -> dict:
    """The type's default as JSON (``@type`` refuses an ``ImageValue``); ``IMAGEField`` builds the image."""
    return {"value": {"width": 0, "height": 0, "layout": layout.value}}


@type_decorator(
    wire_type=DataWire,
    label="Image",
    description="A picture of any channel layout. Pixels are kept as made and converted on demand.",
    color=_COLOR,
    store_strategy=StoreStrategy.NEVER,
    default=_empty_default(Layout.GRAY),
    hidden=False,
)
class IMAGE(CARRIER):
    """A picture of any channel layout; the value is never saved with the graph."""

    element_type_cls = ImageValue
    LAYOUT: ClassVar[Layout | None] = None

    @classmethod
    def empty_value(cls) -> ImageValue:
        """Return the empty image of this type's layout."""
        return ImageValue.empty(cls.LAYOUT or Layout.GRAY)

    def __init__(self, value: Any = None, **kwargs: Any) -> None:
        super().__init__(value, **kwargs)
        self._value = _as_image(self._value)  # the type's default arrives as JSON

    def to_dict(self) -> dict:
        """Describe the image (size and layout); the pixels are not serialized."""
        img = cast(ImageValue, self._value)
        return {"value": {"width": img.width, "height": img.height, "layout": img.layout.value}}

    @classmethod
    def from_dict(cls, data: dict) -> ImageValue:
        """Return the empty image of this type's layout: pixels never round-trip."""
        return ImageValue.empty(cls.LAYOUT or Layout.GRAY)


class IMAGEField(PrimitiveField):
    """DataField for the image types: starts as the empty image of the type's layout."""

    def __post_init__(self) -> None:
        super().__post_init__()
        self._default = _as_image(self._default)
        self._value = self._default

    def _set_own(self, value: Any) -> None:
        self._value = _as_image(value)


def _as_image(value: Any) -> Any:
    if isinstance(value, dict):
        inner = value.get("value", value)
        layout = inner.get("layout") if isinstance(inner, dict) else None
        return ImageValue.empty(Layout(layout) if layout else Layout.GRAY)
    return value


IMAGE.field_class = IMAGEField


@type_decorator(
    wire_type=DataWire,
    label="Gray image",
    description="A one-channel picture.",
    color=_COLOR,
    store_strategy=StoreStrategy.NEVER,
    default=_empty_default(Layout.GRAY),
)
class IMAGE_GRAY(IMAGE):
    """A one-channel picture."""

    LAYOUT: ClassVar[Layout | None] = Layout.GRAY


@type_decorator(
    wire_type=DataWire,
    label="RGB image",
    description="A three-channel picture.",
    color=_COLOR,
    store_strategy=StoreStrategy.NEVER,
    default=_empty_default(Layout.RGB),
)
class IMAGE_RGB(IMAGE):
    """A three-channel picture."""

    LAYOUT: ClassVar[Layout | None] = Layout.RGB


@type_decorator(
    wire_type=DataWire,
    label="RGBA image",
    description="A picture with three colour channels and transparency.",
    color=_COLOR,
    store_strategy=StoreStrategy.NEVER,
    default=_empty_default(Layout.RGBA),
)
class IMAGE_RGBA(IMAGE):
    """A picture with three colour channels and transparency."""

    LAYOUT: ClassVar[Layout | None] = Layout.RGBA

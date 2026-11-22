"""The component API: what a library imports to define nodes, types, widgets and settings.

A name in ``__all__`` carries the compatibility promise of ADR 0085: it is
removed or changed incompatibly only after a minor release in which it was
deprecated. Anything else under ``haywire`` is internal and may move without
notice. Editors, panels, sessions and the design system are in
``haywire.api.workbench``.

    from haywire.api import BaseNode, NodeType, node, ExecutionContext, FLOAT, NumberWidget

Imports and ``__all__`` only; the one function serves deprecated names. Nothing in ``haywire.core``,
``haywire.ui`` or ``haywire.barn`` imports this package, except the node
templates the New Node wizard copies into authors' libraries.
``tests/api/test_author_api.py`` holds the checked-in name list: adding,
removing or renaming a name here fails it until the list is edited.
"""

# haywire.core.node comes first: it fixes the import order of the node, edge,
# graph and types packages, which form a cycle when entered elsewhere.
from __future__ import annotations

from haywire.barn.builtin.carrier import CarrierValue
from haywire.barn.builtin.field_text import fields_from_text, fields_to_text
from haywire.barn.builtin.progress import ProgressSettings, ProgressSpan, progress_field
from haywire.barn.builtin.types import (
    ADD,
    ANNOTATION,
    BOOL,
    BUNDLE,
    CALLBACK,
    CARRIER,
    CHOICES,
    COLOR,
    EXEC,
    FIELD_LIST,
    FILE_PATH,
    FLOAT,
    FOLD,
    FOLDER_PATH,
    INT,
    MAT3,
    MAT4,
    OPTIONAL,
    PATH,
    PROGRESS,
    STRING,
    VEC2F,
    VEC2I,
    VEC3F,
    VEC3I,
    VEC4F,
    VEC4I,
    ADDField,
    CarrierField,
    ColorStr,
    FieldEntry,
    FLOATField,
    INTField,
    is_valid_field_key,
)
from haywire.barn.builtin.widget_keys import (
    ANNOTATION_TEXT_WIDGET,
    ARROW_HEAD_WIDGET,
    BUTTON_WIDGET,
    COLOR_WIDGET,
    FIELD_LIST_WIDGET,
    FOLD_WIDGET,
    LABEL_WIDGET,
    MATRIX_WIDGET,
    MENU_WIDGET,
    NUMBER_WIDGET,
    OPTIONAL_WIDGET,
    PATH_WIDGET,
    PROGRESS_WIDGET,
    SLIDER_WIDGET,
    TEXT_WIDGET,
    TOGGLE_WIDGET,
    VECTOR_WIDGET,
)
from haywire.barn.builtin.widgets import (
    AnnotationTextWidget,
    ArrowHeadWidget,
    ButtonWidget,
    CheckboxWidget,
    ColorWidget,
    FieldListWidget,
    FoldWidget,
    LabelWidget,
    MatrixWidget,
    MenuWidget,
    NumberWidget,
    OptionalWidget,
    PathWidget,
    ProgressWidget,
    SliderWidget,
    TextWidget,
    ToggleWidget,
    VectorWidget,
)
from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire
from haywire.core.adapter.base import BaseAdapter, adapter
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.catalog import CatalogEntry, CatalogRegistry, ModelFile, Resource
from haywire.core.di.context import get_workspace_root
from haywire.core.edge.arrow_heads import NO_ARROW_HEAD
from haywire.core.edge.style import dash_choices
from haywire.core.errors import Refusal, report_failure
from haywire.core.execution import (
    CallbackEvent,
    ExecutionContext,
    QueueMode,
    SystemEvent,
    SystemEventType,
)
from haywire.core.library.base import BaseLibrary
from haywire.core.library.compatibility import CompatibilityWarning
from haywire.core.library.decorator import library
from haywire.core.library.deprecated_names import DeprecatedName, serve_deprecated
from haywire.core.macro import MacroRegistry
from haywire.core.node import BaseNode, NodeRegistry, NodeType, NodeWrapper, node
from haywire.core.node.node_warning import NodeWarning
from haywire.core.settings import (
    EdgeSettings,
    LibrarySettings,
    NodeSettings,
    Promotable,
    Settings,
    SettingsRegistry,
    UiState,
    bag,
    setting,
    settings,
    settings_fields,
    shadow,
    watch,
)
from haywire.core.settings.types import Mat3, Mat4, Vec2f, Vec2i, Vec3f, Vec3i, Vec4f, Vec4i
from haywire.core.skin.fonts import FONT_STACKS, FONTS, TEXT_H_ALIGNS, TEXT_V_ALIGNS
from haywire.core.skin.settings import skin_choices, widget_node_stage_skin_choices
from haywire.core.skin.tags import (
    SKIN_TAG_GENERAL,
    SKIN_TAG_GRAPH_NODE,
    SKIN_TAG_SPECIAL,
    SKIN_TAG_STAGE_ONLY,
    SKIN_TAG_WIDGET_NODE,
)
from haywire.core.storage import library_storage_dir
from haywire.core.tomlio import read_toml, to_builtin, write_toml
from haywire.core.types import (
    BaseType,
    CompoundType,
    DataField,
    DataPort,
    Drained,
    IType,
    LayoutDirection,
    PortOrigin,
    PortType,
    PrimitiveField,
    PrimitiveType,
    StoreStrategy,
    TypeRegistry,
    WireRole,
    WireType,
    declaring_type_of,
    type,
)
from haywire.core.types.enums import ShowWidgetStrategy
from haywire.core.types.event import Event
from haywire.core.types.fields import element_from_dict, element_to_dict
from haywire.core.volumes import (
    VolumeError,
    VolumePath,
    ensure_volume,
    resolve_volume_path,
    volume_location,
    volume_name,
)
from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.pin_render import render_pin
from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.themes import BaseTheme, ThemeRegistry, theme
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.converters import (
    BindingConverter,
    Converters,
    PrimitiveUnwrappingConverter,
)
from haywire.ui.widget.decorator import widget
from haywire.ui.widget.globals import get_widget_class
from haywire.ui.widget.registry import WidgetRegistry

#: Names that left ``__all__`` and are still served, with a notice, until the
#: release each entry names. ``tests/api/names.py`` lists them too.
_DEPRECATED: dict[str, DeprecatedName] = {}


def __getattr__(name: str):
    entry = _DEPRECATED.get(name)
    if entry is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return serve_deprecated(__name__, name, entry)


__all__ = [
    # Library
    "BaseLibrary",
    "CompatibilityWarning",
    "library",
    "library_storage_dir",
    # Registries a library's register_components() names
    "AdapterRegistry",
    "CatalogRegistry",
    "MacroRegistry",
    "NodeRegistry",
    "SettingsRegistry",
    "SkinRegistry",
    "ThemeRegistry",
    "TypeRegistry",
    "WidgetRegistry",
    # Node
    "BaseNode",
    "NodeType",
    "NodeWarning",
    "NodeWrapper",
    "node",
    # Execution
    "CallbackEvent",
    "ExecutionContext",
    "QueueMode",
    "SystemEvent",
    "SystemEventType",
    # Errors
    "Refusal",
    "report_failure",
    # Type
    "BaseType",
    "CompoundType",
    "DataField",
    "DataPort",
    "Drained",
    "Event",
    "IType",
    "LayoutDirection",
    "PortOrigin",
    "PortType",
    "PrimitiveField",
    "PrimitiveType",
    "ShowWidgetStrategy",
    "StoreStrategy",
    "WireRole",
    "declaring_type_of",
    "element_from_dict",
    "element_to_dict",
    "type",
    # Wires
    "CallbackWire",
    "ControlWire",
    "DataWire",
    "EdgeSettings",
    "NO_ARROW_HEAD",
    "WireType",
    "dash_choices",
    # Builtin types (all of haywire.barn.builtin.types)
    "ADD",
    "ADDField",
    "ANNOTATION",
    "BOOL",
    "BUNDLE",
    "CALLBACK",
    "CARRIER",
    "CHOICES",
    "COLOR",
    "CarrierField",
    "ColorStr",
    "EXEC",
    "FIELD_LIST",
    "FILE_PATH",
    "FLOAT",
    "FLOATField",
    "FOLD",
    "FOLDER_PATH",
    "FieldEntry",
    "INT",
    "INTField",
    "MAT3",
    "MAT4",
    "OPTIONAL",
    "PATH",
    "PROGRESS",
    "STRING",
    "VEC2F",
    "VEC2I",
    "VEC3F",
    "VEC3I",
    "VEC4F",
    "VEC4I",
    "is_valid_field_key",
    # Carrier values
    "CarrierValue",
    "fields_from_text",
    "fields_to_text",
    # Adapter
    "BaseAdapter",
    "adapter",
    # Widget
    "BaseWidget",
    "BindingConverter",
    "Converters",
    "PrimitiveUnwrappingConverter",
    "get_widget_class",
    "widget",
    # Builtin widgets (all of haywire.barn.builtin.widgets)
    "AnnotationTextWidget",
    "ArrowHeadWidget",
    "ButtonWidget",
    "CheckboxWidget",
    "ColorWidget",
    "FieldListWidget",
    "FoldWidget",
    "LabelWidget",
    "MatrixWidget",
    "MenuWidget",
    "NumberWidget",
    "OptionalWidget",
    "PathWidget",
    "ProgressWidget",
    "SliderWidget",
    "TextWidget",
    "ToggleWidget",
    "VectorWidget",
    # Builtin widget keys (all of haywire.barn.builtin.widget_keys)
    "ANNOTATION_TEXT_WIDGET",
    "ARROW_HEAD_WIDGET",
    "BUTTON_WIDGET",
    "COLOR_WIDGET",
    "FIELD_LIST_WIDGET",
    "FOLD_WIDGET",
    "LABEL_WIDGET",
    "MATRIX_WIDGET",
    "MENU_WIDGET",
    "NUMBER_WIDGET",
    "OPTIONAL_WIDGET",
    "PATH_WIDGET",
    "PROGRESS_WIDGET",
    "SLIDER_WIDGET",
    "TEXT_WIDGET",
    "TOGGLE_WIDGET",
    "VECTOR_WIDGET",
    # Settings
    "LibrarySettings",
    "NodeSettings",
    "Promotable",
    "Settings",
    "UiState",
    "bag",
    "setting",
    "settings",
    "settings_fields",
    "shadow",
    "watch",
    "Mat3",
    "Mat4",
    "Vec2f",
    "Vec2i",
    "Vec3f",
    "Vec3i",
    "Vec4f",
    "Vec4i",
    # Files and workspace
    "get_workspace_root",
    "to_builtin",
    "read_toml",
    "write_toml",
    # Progress
    "ProgressSettings",
    "ProgressSpan",
    "progress_field",
    # Skin
    "BaseSkin",
    "FONTS",
    "FONT_STACKS",
    "TEXT_H_ALIGNS",
    "SKIN_TAG_GENERAL",
    "SKIN_TAG_GRAPH_NODE",
    "SKIN_TAG_SPECIAL",
    "SKIN_TAG_STAGE_ONLY",
    "SKIN_TAG_WIDGET_NODE",
    "TEXT_V_ALIGNS",
    "render_pin",
    "skin",
    "skin_choices",
    "widget_node_stage_skin_choices",
    # Theme
    "BaseTheme",
    "theme",
    # Catalog
    "CatalogEntry",
    "ModelFile",
    "Resource",
    # Volumes
    "VolumeError",
    "VolumePath",
    "ensure_volume",
    "resolve_volume_path",
    "volume_location",
    "volume_name",
]

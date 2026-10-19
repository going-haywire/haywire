"""The default skins, their settings and the Skin panel ship in haybale-graph-editor (ADR 0057)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.skin.factory import SkinFactory

pytestmark = [pytest.mark.integration]

GE = "haybale-graph-editor"
_GE_ROOT = Path(__file__).resolve().parents[3] / "barn/haybale-graph-editor"


def test_default_and_error_skins_live_in_graph_editor(library_system) -> None:
    registry = library_system.injector.get(SkinFactory)._skin_registry
    assert registry.get_default_skin_registry_key() == f"{GE}:skin:StackedNodeSkin"
    assert registry.get_error_skin_registry_key() == f"{GE}:skin:ErrorNodeSkin"
    assert registry.has(f"{GE}:skin:SplitNodeSkin")
    assert not [key for key in registry.list_names() if key.startswith("haybale-studio:skin:")]


def test_node_skin_settings_keep_their_namespace() -> None:
    from haybale_graph_editor.settings.node_skin_settings import NodeSkinSettings

    assert NodeSkinSettings._namespace == "ui.node.skin"
    assert NodeSkinSettings._settings_descriptors()["pin_gutter"]._setting_key == "ui.node.skin.pin_gutter"


def test_skin_settings_panel_lives_in_graph_editor(library_system) -> None:
    from haywire.barn.builtin.surfaces import CanvasSettings

    panels = library_system.injector.get(PanelRegistry)
    assert panels.has(f"{GE}:panel:NodeSkinSettingsPanel")
    assert not panels.has("haybale-studio:panel:NodeSkinSettingsPanel")
    identity = panels.get(f"{GE}:panel:NodeSkinSettingsPanel").class_identity
    assert identity.surface.id == CanvasSettings.id
    assert identity.label == "Skin"
    assert identity.order == 20


def test_graph_editor_never_imports_haybale_studio() -> None:
    offenders = [
        path
        for path in (_GE_ROOT / "haybale_graph_editor").rglob("*.py")
        if re.search(r"\bhaybale_studio\b", path.read_text())
    ]
    assert offenders == []
    assert "haybale-studio" not in (_GE_ROOT / "pyproject.toml").read_text()


def test_graph_editor_scans_settings_before_skins(monkeypatch) -> None:
    from haybale_graph_editor import Library

    order: list[str] = []
    library = Library.__new__(Library)
    library._registry_folders = {}

    def declare(self, folder_path: str, registry_cls: type, exclude_patterns=None) -> None:
        self._registry_folders[registry_cls] = (folder_path, exclude_patterns)

    def scan(self, folder_path: str, registry_cls: type, exclude_patterns=None) -> None:
        order.append(Path(folder_path).name)

    monkeypatch.setattr(Library, "add_folder_to_registry", declare)
    monkeypatch.setattr(Library, "_register_folder", scan)
    monkeypatch.setattr(Library, "is_watched", property(lambda self: False))
    library.register_components()
    library._attach_to_registries()

    assert "settings" in order
    assert order.index("settings") < order.index("skins")
    assert order.index("settings") < order.index("panels")


def test_an_old_studio_skin_key_renders_the_error_card(
    library_system, nicegui_slot_context, monkeypatch
) -> None:
    from haybale_testing.nodes.testbed.display_node import DisplayNode

    factory = library_system.injector.get(SkinFactory)
    error_skin = factory.get_skin_instance(factory._skin_registry.get_error_skin_registry_key())
    calls: list[str] = []
    real_render = type(error_skin).render

    def spy(self, main_card, wrapper, *, on_stage):
        calls.append(wrapper.node_id)
        return real_render(self, main_card, wrapper, on_stage=on_stage)

    monkeypatch.setattr(type(error_skin), "render", spy)
    graph = BaseGraph(filestem="old skin key", validation_scheduler=SyncScheduler())
    wrapper = graph.create_node_wrapper(DisplayNode.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None

    card = factory.render("haybale-studio:skin:StackedNodeSkin", wrapper, on_stage=False)

    assert card is not None
    assert calls == [wrapper.node_id]

import pytest
from haywire.core.di.config import create_library_system_service
from haywire_studio.docs_gen.extract import extract_library


@pytest.fixture(scope="module")
def service(project_root):
    svc = create_library_system_service(
        workspace_root=str(project_root),
        enable_file_watching=False,
        watch_settings=False,
    )
    yield svc


@pytest.mark.integration
def test_extract_collects_components_with_identity(service):
    doc = extract_library(service, "testing")
    assert doc.library_id == "testing"
    assert doc.components, "testing library should expose components"
    for rec in doc.components:
        assert rec.registry_key.split(":")[0] == "testing"
        assert rec.kind in {
            "node",
            "type",
            "adapter",
            "widget",
            "skin",
            "setting",
            "theme",
            "panel",
            "editor",
            "state",
            "farmhand",
        }
        assert isinstance(rec.label, str)


@pytest.mark.integration
def test_extract_farmhand_carries_input_schema(service):
    doc = extract_library(service, "testing")
    farmhands = [r for r in doc.components if r.kind == "farmhand"]
    if farmhands:
        assert "input_schema" in farmhands[0].extra

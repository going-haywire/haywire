from __future__ import annotations

from pathlib import Path

from haywire.core.di.config import create_library_system_service
from haywire.core.library.registry import LibraryRegistry
from haywire_studio.docs_gen.extract import extract_library
from haywire_studio.docs_gen.render import (
    coverage_report,
    doc_filename,
    render_component,
    render_overview,
    render_quickref,
    render_readme,
)


def _module_dir(library_path: Path) -> Path:
    """The package's importable module directory (contains __init__.py)."""
    if (library_path / "__init__.py").exists():
        return library_path
    for child in sorted(library_path.iterdir()):
        if child.is_dir() and (child / "__init__.py").exists():
            return child
    raise FileNotFoundError(f"No module directory under {library_path}")


def _library_id_for_path(service, library_path: Path) -> str:
    """Match the loaded library whose folder_path is under library_path."""
    registry = service.injector.get(LibraryRegistry)
    target = library_path.resolve()
    for lib_id in registry.list_names():
        folder = Path(registry.get_library_identity(lib_id).folder_path).resolve()
        if folder == target or target in folder.parents or folder in target.parents:
            return lib_id
    raise ValueError(f"No loaded library found under {library_path}")


def generate_docs(library_path: str | None) -> list[str]:
    lib_root = Path(library_path).resolve() if library_path else Path.cwd()
    module_dir = _module_dir(lib_root)

    service = create_library_system_service(
        workspace_root=str(lib_root),
        enable_file_watching=False,
        watch_settings=False,
    )
    library_id = _library_id_for_path(service, lib_root)
    doc = extract_library(service, library_id)

    (module_dir / "OVERVIEW.md").write_text(render_overview(doc), encoding="utf-8")
    (module_dir / "QUICKREF.md").write_text(render_quickref(doc), encoding="utf-8")

    docs_dir = module_dir / "docs"
    docs_dir.mkdir(exist_ok=True)
    for rec in doc.components:
        (docs_dir / doc_filename(rec.registry_key)).write_text(render_component(rec), encoding="utf-8")

    notes_path = module_dir / "NOTES.md"
    notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
    readme_path = lib_root / "README.md"
    existing = readme_path.read_text(encoding="utf-8") if readme_path.exists() else None
    readme_path.write_text(render_readme(doc, notes, existing), encoding="utf-8")

    return coverage_report(doc)

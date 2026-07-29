import pytest
from haywire_studio.docs_gen.generate import generate_docs


@pytest.mark.integration
def test_generate_writes_expected_files(tmp_path, monkeypatch):
    # Point at the in-repo haybale-testing library (package root).
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    lib_root = repo / "barn" / "haybale-testing"
    coverage = generate_docs(str(lib_root))
    module_dir = lib_root / "haybale_testing"
    assert (module_dir / "OVERVIEW.md").exists()
    assert (module_dir / "QUICKREF.md").exists()
    assert (module_dir / "docs").is_dir()
    assert (lib_root / "README.md").exists()
    assert isinstance(coverage, list)

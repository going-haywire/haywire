from haybale_marketplace.editors.library_overview_editor import collect_overview_links
from haywire.core.marketstall.types import Haybale


def test_examples_link_present_when_url_set():
    pkg = Haybale(
        name="lib",
        version="1.0.0",
        source_url="https://github.com/me/repo",
        docs_url="https://raw.example.com/lib/",
        examples_url="https://raw.example.com/lib/examples/",
        tests_url="https://raw.example.com/lib/tests/",
    )
    links = collect_overview_links(pkg)
    labels = [lbl for lbl, _ in links]
    assert "Examples" in labels
    assert "Tests" not in labels  # tests_url is quiet metadata, not surfaced
    assert "Docs" in labels
    assert "Source" in labels


def test_no_examples_link_when_url_absent():
    pkg = Haybale(name="lib", version="1.0.0", source_url="https://github.com/me/repo")
    assert "Examples" not in [lbl for lbl, _ in collect_overview_links(pkg)]

from haybale_marketplace.editors.library_overview_editor import collect_overview_links
from haywire.core.marketstall.types import Haybale

_SPEC = "lib @ git+https://github.com/me/repo.git@v1.2.3#subdirectory=barn/lib"


def test_examples_link_present_when_path_set():
    pkg = Haybale(
        name="lib",
        version="1.0.0",
        origin="https://github.com/me/repo",
        install_spec=_SPEC,
        notes="NOTES.md",
        examples_path="barn/lib/examples/",
        tests_path="barn/lib/tests/",
    )
    links = collect_overview_links(pkg)
    labels = [lbl for lbl, _ in links]
    assert "Examples" in labels
    assert "Tests" not in labels  # tests_path is quiet metadata, not surfaced
    assert "Notes" in labels
    assert "Source" in labels


def test_directory_paths_link_to_the_tree_form():
    """A trailing slash is a directory; /blob/ on a directory 404s."""
    pkg = Haybale(
        name="lib",
        version="1.0.0",
        origin="https://github.com/me/repo",
        install_spec=_SPEC,
        examples_path="barn/lib/examples/",
    )
    examples = dict(collect_overview_links(pkg))["Examples"]
    assert examples == "https://github.com/me/repo/tree/v1.2.3/barn/lib/examples/"


def test_notes_links_to_the_blob_form_inside_the_module_dir():
    """`notes` is a bare filename; the module directory it sits in is derived
    from install_spec rather than stored."""
    pkg = Haybale(
        name="lib",
        version="1.0.0",
        origin="https://github.com/me/repo",
        install_spec=_SPEC,
        notes="NOTES.md",
    )
    notes = dict(collect_overview_links(pkg))["Notes"]
    assert notes == "https://github.com/me/repo/blob/v1.2.3/barn/lib/lib/NOTES.md"


def test_documentation_url_is_used_verbatim():
    """An absolute URL to a rendered site — nothing to resolve it against."""
    pkg = Haybale(
        name="lib",
        version="1.0.0",
        origin="https://github.com/me/repo",
        install_spec=_SPEC,
        documentation_url="https://me.github.io/repo/",
    )
    assert dict(collect_overview_links(pkg))["Documentation"] == "https://me.github.io/repo/"


def test_links_resolve_against_the_install_spec_ref():
    pkg = Haybale(
        name="lib",
        version="1.0.0",
        origin="https://github.com/me/repo",
        install_spec=_SPEC,
        examples_path="barn/lib/examples/OVERVIEW.md",
    )
    assert dict(collect_overview_links(pkg))["Examples"] == (
        "https://github.com/me/repo/blob/v1.2.3/barn/lib/examples/OVERVIEW.md"
    )


def test_unresolvable_path_is_dropped_rather_than_guessed():
    """No install_spec means no ref; a link that guessed one would 404."""
    pkg = Haybale(
        name="lib",
        version="1.0.0",
        origin="https://github.com/me/repo",
        notes="NOTES.md",
    )
    labels = [lbl for lbl, _ in collect_overview_links(pkg)]
    assert labels == ["Source"]


def test_no_examples_link_when_path_absent():
    pkg = Haybale(name="lib", version="1.0.0", origin="https://github.com/me/repo")
    assert "Examples" not in [lbl for lbl, _ in collect_overview_links(pkg)]

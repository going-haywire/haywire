"""Sample package init used by tests for the marketstall generator's @library parser.

Parsed as TEXT by the generator — never imported as Python, so the bare
``@library`` name below is intentionally undefined.
"""

# mypy: ignore-errors

from importlib.metadata import version as _pkg_version


@library(  # noqa: F821  (fake import; this file is a fixture, never imported as Python)
    label="Alpha",
    id="alpha",
    version=_pkg_version("haybale-alpha"),
    description="Alpha library — overridden in pyproject? Decorator wins.",
    url="",
    author="Alpha Author",
    author_url="",
    linked_libraries=["haybale_beta"],
    tags=["alpha", "demo"],
    file_watcher=False,
)
class Library:
    pass

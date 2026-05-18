"""Sample package init used by tests for the marketstall generator's @library parser."""

from importlib.metadata import version as _pkg_version


@library(  # noqa: F821  (fake import; this file is a fixture, never imported as Python)
    label="Alpha",
    id="alpha",
    version=_pkg_version("haybale-alpha"),
    description="Alpha library — overridden in pyproject? Decorator wins.",
    url="",
    help_url="",
    author="Alpha Author",
    author_url="",
    dependencies=["haybale_beta"],
    tags=["alpha", "demo"],
    file_watcher=False,
)
class Library:
    pass

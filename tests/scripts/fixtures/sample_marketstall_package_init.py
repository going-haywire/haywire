"""Sample package init used by tests for the marketstall generator's @library parser.

Parsed as TEXT by the generator — never imported as Python, so the bare
``@library`` name below is intentionally undefined.
"""

# mypy: ignore-errors


@library(  # noqa: F821  (fake import; this file is a fixture, never imported as Python)
    label="Alpha",
    id="alpha",
    linked_libraries=["haybale_beta"],
    file_watcher=False,
)
class Library:
    pass

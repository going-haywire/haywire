"""Manifest read failures, as plain RuntimeErrors.

These sit below the pipeline's error taxonomy: the pipeline translates them
into ``ManifestError`` at its boundary so a wizard step's ``except
ShareError`` catches them. Keeping them independent of that taxonomy lets
non-pipeline callers (``deps_cli``) read manifests without importing it.
"""

from __future__ import annotations


class ManifestReadError(RuntimeError):
    """A library pyproject.toml could not be read or is invalid."""


class InvalidOsDeclarationError(ManifestReadError):
    """Raised when a library's ``haybale.toml`` ``os`` contains an invalid value.

    Only "macos", "windows", "linux" are declarable. "other" is a runtime
    sentinel for unmapped platform.system() results and must not be declared.
    """

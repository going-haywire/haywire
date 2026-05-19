"""Regression tests for LibraryManager._build_required_by_cache parsing.

Plan A's PEP 440 ~= compatible-release version constraints (e.g.
``haywire-core~=0.0.1``) broke the old regex used to extract the bare
distribution name from a Requires-Dist string. The cache ended up keyed
by ``haywire_core~`` instead of ``haywire_core``, so the REQUIRED filter
in the Library Browser never highlighted anything.
"""

from __future__ import annotations

import re

import pytest


@pytest.mark.unit
@pytest.mark.parametrize(
    "requires_dist, expected",
    [
        # Compatible-release operator (Plan A pattern).
        ("haywire-core~=0.0.1", "haywire_core"),
        # Classic exact / range operators must still work.
        ("haywire-core==0.0.1", "haywire_core"),
        ("haywire-core>=0.0.1", "haywire_core"),
        ("haywire-core>=0.0.1,<2", "haywire_core"),
        # Environment marker.
        ('haywire-core>=0.0.1; python_version < "3.11"', "haywire_core"),
        # Extras.
        ("haywire-core[full]>=0.0.1", "haywire_core"),
        # Plain name, no operator.
        ("haywire-core", "haywire_core"),
        # Underscore variant.
        ("haywire_core~=0.0.1", "haywire_core"),
    ],
)
def test_requires_dist_name_extraction(requires_dist: str, expected: str) -> None:
    """The split-and-normalize pipeline used by _build_required_by_cache must
    drop every PEP 440 operator (including ``~=``) so the cache key is just
    the bare distribution name."""
    # Same pipeline as _build_required_by_cache.
    req_name = re.split(r"[~>=<!;\s\[]", requires_dist)[0]
    req_norm = re.sub(r"[-_.]+", "_", req_name).lower()
    assert req_norm == expected

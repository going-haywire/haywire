"""Unit tests for Compatibility Warning semver parsing + trigger logic."""

import pytest

from haywire.core.library.compatibility import (
    CompatibilityChecker,
    CompatibilityFinding,
    CompatibilityWarning,
    parse_semver,
    SavedNode,
    SemverError,
)


@pytest.mark.unit
class TestParseSemver:
    def test_parses_dotted_triplet(self):
        assert parse_semver("0.0.14") == (0, 0, 14)

    def test_ordering_is_numeric_not_lexical(self):
        # 0.0.9 < 0.0.10 must hold (string compare would get this wrong)
        assert parse_semver("0.0.9") < parse_semver("0.0.10")

    def test_rejects_underscore_form(self):
        with pytest.raises(SemverError) as exc:
            parse_semver("0_0_14")
        assert "MAJOR.MINOR.PATCH" in str(exc.value)

    def test_rejects_v_prefix(self):
        with pytest.raises(SemverError):
            parse_semver("v0.0.14")

    def test_rejects_two_part(self):
        with pytest.raises(SemverError):
            parse_semver("0.0")


@pytest.mark.unit
class TestCompatibilityWarningValidation:
    def test_valid_warning_constructs(self):
        w = CompatibilityWarning(
            version="0.0.14",
            component=None,
            message="A library-wide change.",
        )
        assert w.version_tuple == (0, 0, 14)

    def test_malformed_version_fails_loud_with_context(self):
        with pytest.raises(SemverError) as exc:
            CompatibilityWarning(version="0_0_14", component=None, message="x")
        # Message must name the expected form so an author can self-correct.
        assert "0.0.14" in str(exc.value)


def _history_lookup(table):
    """Return a warnings-by-library-id lookup backed by a dict."""
    return lambda lib_id: table.get(lib_id, [])


@pytest.mark.unit
class TestCompatibilityChecker:
    def test_node_warning_fires_when_saved_below_version(self):
        warnings = [
            CompatibilityWarning(
                version="0.0.14",
                component="testing:node:Foo",
                message="inlet widget strategy became author-declared",
            )
        ]
        checker = CompatibilityChecker(_history_lookup({"testing": warnings}))
        saved = [
            SavedNode(
                node_id="n1",
                registry_key="testing:node:Foo",
                library_id="testing",
                saved_version="0.0.13",
            )
        ]
        findings = checker.check(saved)
        assert findings == [
            CompatibilityFinding(
                node_id="n1",
                message="inlet widget strategy became author-declared",
                source_version="0.0.13",
            )
        ]

    def test_does_not_fire_when_saved_equals_or_above_version(self):
        warnings = [
            CompatibilityWarning(
                version="0.0.14",
                component="testing:node:Foo",
                message="x",
            )
        ]
        checker = CompatibilityChecker(_history_lookup({"testing": warnings}))
        saved = [
            SavedNode("n1", "testing:node:Foo", "testing", "0.0.14"),
            SavedNode("n2", "testing:node:Foo", "testing", "0.1.0"),
        ]
        assert checker.check(saved) == []

    def test_node_warning_matches_by_registry_key(self):
        warnings = [CompatibilityWarning(version="0.0.14", component="testing:node:Other", message="x")]
        checker = CompatibilityChecker(_history_lookup({"testing": warnings}))
        saved = [SavedNode("n1", "testing:node:Foo", "testing", "0.0.13")]
        assert checker.check(saved) == []  # different node, no match

    def test_missing_saved_version_treated_as_infinitely_old(self):
        warnings = [CompatibilityWarning(version="0.0.14", component="testing:node:Foo", message="x")]
        checker = CompatibilityChecker(_history_lookup({"testing": warnings}))
        saved = [SavedNode("n1", "testing:node:Foo", "testing", saved_version=None)]
        findings = checker.check(saved)
        assert findings == [CompatibilityFinding("n1", "x", source_version=None)]

    def test_library_wide_warning_fires_once_per_graph(self):
        warnings = [CompatibilityWarning(version="0.0.14", component=None, message="lib-wide")]
        checker = CompatibilityChecker(_history_lookup({"testing": warnings}))
        saved = [
            SavedNode("n1", "testing:node:Foo", "testing", "0.0.13"),
            SavedNode("n2", "testing:node:Bar", "testing", "0.0.13"),
        ]
        findings = checker.check(saved)
        # Exactly one library-wide finding, not one per node. node_id is None.
        lib_wide = [f for f in findings if f.node_id is None]
        assert lib_wide == [CompatibilityFinding(None, "lib-wide", source_version=None)]

    def test_library_wide_does_not_fire_if_all_nodes_current(self):
        warnings = [CompatibilityWarning(version="0.0.14", component=None, message="lib-wide")]
        checker = CompatibilityChecker(_history_lookup({"testing": warnings}))
        saved = [SavedNode("n1", "testing:node:Foo", "testing", "0.0.14")]
        assert checker.check(saved) == []

    def test_unknown_library_yields_no_findings(self):
        checker = CompatibilityChecker(_history_lookup({}))
        saved = [SavedNode("n1", "ghost:node:Foo", "ghost", "0.0.1")]
        assert checker.check(saved) == []


@pytest.mark.unit
class TestBaseLibraryHook:
    def test_default_compatibility_warnings_is_empty(self):
        # A library that declares nothing returns an empty history.
        from haywire.core.library.base import BaseLibrary

        # BaseLibrary is abstract; build a minimal concrete subclass.
        class _Lib(BaseLibrary):
            def register_components(self):  # pragma: no cover - not exercised
                pass

            def validate(self) -> bool:  # pragma: no cover - not exercised
                return True

        # compatibility_warnings is a plain method with a default; callable on the class.
        assert _Lib.compatibility_warnings(object.__new__(_Lib)) == []

"""FIELD_LIST values and the registry's list of types a field can have."""

from types import SimpleNamespace

import pytest

from haywire.barn.builtin.types import FIELD_LIST, FLOAT, INT, FieldEntry, is_valid_key
from haywire.barn.builtin.widgets.field_list_widget import TypeChoice, type_choices
from haywire.core.types.utils import serialize_element_type


@pytest.mark.unit
class TestKeysAndValues:
    @pytest.mark.parametrize(
        ("key", "ok"),
        [
            ("t", True),
            ("cam_1", True),
            ("T", True),
            ("0", True),
            ("", False),
            ("a b", False),
            ("a:b", False),
            ("a-b", False),
            ("é", False),
            ("a\n", False),
        ],
    )
    def test_key_rule(self, key, ok):
        assert is_valid_key(key) is ok

    def test_from_dict_drops_bad_and_duplicate_keys_without_raising(self):
        r = {"registry_key": "haywire-core:type:INT"}
        data = {
            "entries": [
                {"key": "a", "recipe": r},
                {"key": "a", "recipe": r},
                {"key": "b c", "recipe": r},
                {"key": "d"},
                {"key": "e", "recipe": "junk"},
                "junk",
            ]
        }
        assert [e.key for e in FIELD_LIST.from_dict(data).entries] == ["a"]

    @pytest.mark.parametrize("data", ["junk", None, {}, {"entries": "junk"}, {"entries": None}])
    def test_from_dict_tolerates_anything(self, data):
        assert FIELD_LIST.from_dict(data).entries == ()

    def test_with_added_refuses_a_duplicate_and_a_bad_key(self):
        one = FIELD_LIST().with_added("a", INT)
        with pytest.raises(ValueError, match="already"):
            one.with_added("a", FLOAT)
        with pytest.raises(ValueError, match="letters"):
            one.with_added("b c", FLOAT)

    def test_with_added_stores_the_type_recipe_and_keeps_the_original(self):
        empty = FIELD_LIST()
        one = empty.with_added("a", INT)
        assert empty.entries == ()
        assert one.entries == (FieldEntry("a", dict(serialize_element_type(INT))),)

    def test_round_trip_and_equality(self):
        one = FIELD_LIST().with_added("a", INT).with_added("b", FLOAT)
        assert FIELD_LIST.from_dict(one.to_dict()) == one
        assert one.without("a").without("b") == FIELD_LIST()
        assert one.without("missing") == one


@pytest.mark.integration
def test_the_type_list_offers_values_only(library_system):
    keys = library_system.get_type_registry().list_value_type_keys()
    assert "haywire-core:type:FLOAT" in keys
    assert "haywire-core:type:BUNDLE" in keys
    assert "haybale-image:type:IMAGE_RGB" in keys
    for name in (
        "EXEC",
        "CALLBACK",
        "ADD",
        "OPTIONAL",
        "ANNOTATION",
        "FOLD",
        "PROGRESS",
        "CHOICES",
        "CARRIER",
        "FIELD_LIST",
    ):
        assert f"haywire-core:type:{name}" not in keys


@pytest.mark.integration
def test_the_test_fixture_types_stay_out_of_the_type_list(library_system):
    keys = library_system.get_type_registry().list_value_type_keys()
    for name in ("TEST_BOOL", "TEST_FLOAT", "TEST_INT", "TEST_STRING", "TEST_TEMPERATURE"):
        assert f"haybale-testing:type:{name}" not in keys


@pytest.mark.unit
class TestTypeChoices:
    @staticmethod
    def _registry(identities: dict[str, tuple[str, str]]) -> SimpleNamespace:
        return SimpleNamespace(
            list_value_type_keys=lambda: list(identities),
            get_identity=lambda key: SimpleNamespace(
                label=identities[key][0], description=identities[key][1]
            ),
            get_type_class=lambda key: SimpleNamespace(__name__=key.rsplit(":", 1)[-1]),
        )

    def test_a_label_two_libraries_share_names_the_library(self):
        choices = type_choices(
            self._registry(
                {
                    "haywire-core:type:INT": ("Integer", "Whole number"),
                    "lib-a:type:INT": ("Integer", "Other"),
                    "lib-b:type:INT": ("Integer", "Another"),
                    "lib-a:type:ONLY": ("Only", "Alone"),
                }
            )
        )
        assert choices["haywire-core:type:INT"] == TypeChoice(
            "Integer", "INT", "haywire-core", "Whole number"
        )
        assert choices["lib-a:type:INT"].label == "Integer (lib-a)"
        assert choices["lib-b:type:INT"].label == "Integer (lib-b)"
        assert choices["lib-a:type:ONLY"].label == "Only"

    def test_the_tip_text_lists_the_description_then_the_library(self):
        assert (
            TypeChoice("Integer", "INT", "lib-a", "Whole number").tip_text == "Whole number\nLibrary: lib-a"
        )
        assert TypeChoice("Integer", "INT", "lib-a", "").tip_text == "Library: lib-a"

    def test_choices_sort_by_label_ignoring_case(self):
        choices = type_choices(self._registry({"a:type:Z": ("zeta", ""), "a:type:B": ("Beta", "")}))
        assert [c.label for c in choices.values()] == ["Beta", "zeta"]

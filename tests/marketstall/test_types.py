from haywire.core.marketstall.parsing import parse_marketstall_body
from haywire.core.marketstall.types import Haybale


def test_haybale_round_trips_examples_and_tests_path():
    hb = Haybale(
        name="lib",
        version="1.0.0",
        examples_path="barn/lib/examples/",
        tests_path="barn/lib/tests/",
    )
    d = hb.to_dict()
    assert d["examples_path"] == "barn/lib/examples/"
    assert d["tests_path"] == "barn/lib/tests/"


def test_empty_paths_are_omitted_from_toml_dict():
    hb = Haybale(name="lib", version="1.0.0")
    d = hb.to_dict()
    assert "examples_path" not in d
    assert "tests_path" not in d


def test_parse_reads_examples_and_tests_path():
    body = (
        "[[haybales]]\n"
        'name = "lib"\n'
        'version = "1.0.0"\n'
        'examples_path = "barn/lib/examples/"\n'
        'tests_path = "barn/lib/tests/"\n'
    )
    hb = parse_marketstall_body(body)[0]
    assert hb.examples_path.endswith("/examples/")
    assert hb.tests_path.endswith("/tests/")

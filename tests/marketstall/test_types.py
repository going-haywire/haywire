from haywire.core.marketstall.parsing import parse_marketstall_body
from haywire.core.marketstall.types import Haybale


def test_haybale_round_trips_examples_and_tests_url():
    hb = Haybale(
        name="lib",
        min_version="1.0.0",
        examples_url="https://raw.example.com/lib/examples/",
        tests_url="https://raw.example.com/lib/tests/",
    )
    d = hb.to_dict()
    assert d["examples_url"] == "https://raw.example.com/lib/examples/"
    assert d["tests_url"] == "https://raw.example.com/lib/tests/"


def test_empty_urls_are_omitted_from_toml_dict():
    hb = Haybale(name="lib", min_version="1.0.0")
    d = hb.to_dict()
    assert "examples_url" not in d
    assert "tests_url" not in d


def test_parse_reads_examples_and_tests_url():
    body = (
        "[[haybales]]\n"
        'name = "lib"\n'
        'min_version = "1.0.0"\n'
        'examples_url = "https://raw.example.com/lib/examples/"\n'
        'tests_url = "https://raw.example.com/lib/tests/"\n'
    )
    hb = parse_marketstall_body(body)[0]
    assert hb.examples_url.endswith("/examples/")
    assert hb.tests_url.endswith("/tests/")

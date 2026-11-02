"""DisplayTextConverter: a label shows text and numbers as they are, anything else in its text form."""

import pytest

from haywire.core.volumes import VolumePath
from haywire.ui.widget.converters import DisplayTextConverter

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("value", ["abc", 3, 2.5, True])
def test_text_and_numbers_pass_unchanged(value):
    assert DisplayTextConverter().to_view(value) == value


def test_none_gives_the_default():
    assert DisplayTextConverter(default_value="").to_view(None) == ""


def test_a_path_shows_in_its_text_form():
    path = VolumePath("haywire-core:volume:project", "in/a.png", base="in")
    assert DisplayTextConverter().to_view(path) == str(path)

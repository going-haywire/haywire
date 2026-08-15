"""The clipboard script must work outside a secure context (LAN studio over http)."""

import json

import pytest

from haywire.ui.elements.elements import clipboard_script


def test_prefers_the_clipboard_api_in_a_secure_context():
    script = clipboard_script("hello")
    assert "navigator.clipboard" in script
    assert "isSecureContext" in script


def test_falls_back_to_exec_command():
    """The whole point: navigator.clipboard is undefined on a LAN IP over http."""
    script = clipboard_script("hello")
    assert "execCommand" in script
    assert "textarea" in script.lower()


def test_returns_a_boolean_so_the_caller_can_report_failure():
    script = clipboard_script("hello")
    assert "return true" in script
    assert "return false" in script


def test_removes_the_temporary_element_again():
    assert "removeChild" in clipboard_script("hello")


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "with 'single' quotes",
        'with "double" quotes',
        "with\nnewline",
        "with </script> tag",
        "with \\ backslash",
        "with `backtick` and ${template}",
        "",
    ],
)
def test_value_is_json_encoded_not_interpolated(value):
    """A token or a path could contain anything — never build JS by concatenation."""
    script = clipboard_script(value)
    assert json.dumps(value) in script


def test_a_quote_in_the_value_cannot_break_out_of_the_string():
    script = clipboard_script('"; alert(1); //')
    assert "alert(1)" not in script.replace(json.dumps('"; alert(1); //'), "")

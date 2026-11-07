"""Fields on a carrier as text, for a file that holds them; see ``fields_to_text``."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from haywire.barn.builtin.carrier import Stamp
from haywire.barn.builtin.types import is_valid_key
from haywire.core.di.context import get_type_registry
from haywire.core.types.enums import StoreStrategy

#: Largest text one field may take, in bytes.
MAX_FIELD_BYTES = 1024 * 1024

_VERSION = 1


def can_be_saved(identity: Any) -> bool:
    """Return whether a type's values may be written to a file: its identity is not ``NEVER``.

    A value of such a type can still fail when written; see ``fields_to_text``.

    Args:
        identity: The type's ``class_identity``.
    """
    return not identity.store_strategy & StoreStrategy.NEVER


def _type_name(type_key: str) -> str:
    type_cls = get_type_registry().get_type_class(type_key)
    return type_cls.__name__ if type_cls is not None else type_key


def _encode(stamp: Stamp) -> tuple[str, Any]:
    """Return why ``stamp`` cannot be stored (empty if it can), and its stored form."""
    type_cls = get_type_registry().get_type_class(stamp.type_key)
    if type_cls is None:
        return "this type is not installed", None
    if not can_be_saved(type_cls.class_identity):
        return "this type is not saved", None
    try:
        field = type_cls.create_field()
        field.set_value(stamp.value)
        data = field.to_dict()
        text = json.dumps(data, sort_keys=True)
        back = type_cls.create_field()
        back.from_dict(json.loads(text))
        # The text is compared, since NaN never equals itself and arrays have no plain ==.
        same = json.dumps(back.to_dict(), sort_keys=True) == text
    except Exception as exc:  # a library's type can raise anything from its own conversion
        return f"its value cannot be stored: {exc}", None
    if not same:
        return "its value does not read back the same", None
    if len(text.encode()) > MAX_FIELD_BYTES:
        return f"its value is larger than {MAX_FIELD_BYTES} bytes", None
    return "", data


def fields_to_text(fields: Mapping[str, Stamp]) -> str:
    """Return ``fields`` as text that ``fields_from_text`` reads back.

    Each field is checked: its type must not be declared ``NEVER``, its value must
    convert to JSON, fit ``MAX_FIELD_BYTES`` and come back the same.

    Raises:
        ValueError: A field cannot be stored. The message names every such field.

    Example::

        text = fields_to_text(image.fields)
        fields, problems = fields_from_text(text)
        restored = image.with_fields(fields)
    """
    entries: dict[str, Any] = {}
    problems: list[str] = []
    for key, stamp in fields.items():
        problem, data = _encode(stamp)
        if problem:
            problems.append(f"{key} ({_type_name(stamp.type_key)}, {problem})")
        else:
            entries[key] = {"type": stamp.type_key, "data": data}
    if problems:
        raise ValueError(f"Cannot write fields: {', '.join(problems)}")
    return json.dumps({"version": _VERSION, "fields": entries})


def _decode(key: Any, entry: Any) -> Stamp | str:
    """Return the ``Stamp`` an entry holds, or why it was left out."""
    if not is_valid_key(key):
        return f"Field {key!r} was left out: not a valid key"
    if not isinstance(entry, dict) or not isinstance(entry.get("type"), str) or "data" not in entry:
        return f"Field {key!r} was left out: it is malformed"
    type_key = entry["type"]
    type_cls = get_type_registry().get_type_class(type_key)
    if type_cls is None:
        return f"Field {key!r} was left out: its type {type_key} is not installed"
    if not can_be_saved(type_cls.class_identity):
        return f"Field {key!r} was left out: type {type_key} is not saved in files"
    try:
        field = type_cls.create_field()
        field.from_dict(entry["data"])
        # Reading back through to_dict refuses what from_dict lets through unchecked.
        field.to_dict()
    except Exception as exc:  # the text comes from a file, and a library's type can raise anything
        return f"Field {key!r} was left out: {exc}"
    return Stamp(field.get_value(), type_key)


def fields_from_text(text: str) -> tuple[dict[str, Stamp], list[str]]:
    """Return the fields ``text`` holds, and a sentence for each one left out.

    Only JSON is read, and a type declared ``NEVER`` is refused, so a file cannot make
    anything but a stored value. Text that holds no readable fields gives no fields and
    one sentence.
    """
    try:
        doc = json.loads(text)
    except ValueError:
        return {}, ["The saved fields could not be read: they are not valid text"]
    entries = doc.get("fields") if isinstance(doc, dict) and doc.get("version") == _VERSION else None
    if not isinstance(entries, dict):
        return {}, ["The saved fields could not be read: their format is not known"]
    fields: dict[str, Stamp] = {}
    problems: list[str] = []
    for key, entry in entries.items():
        decoded = _decode(key, entry)
        if isinstance(decoded, Stamp):
            fields[key] = decoded
        else:
            problems.append(decoded)
    return fields, problems

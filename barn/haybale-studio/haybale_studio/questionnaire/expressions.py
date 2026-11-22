"""The condition grammar of a Questionnaire: ``visibleIf``, ``enableIf`` and ``requiredIf``.

A small subset of SurveyJS expressions, parsed into a tree and evaluated
against the answers; nothing is ever passed to ``eval``. See ADR 0083.

- References: ``{name}``. A Check's value is its verdict (``'pass'``, ``'fail'``,
  ``'blocked'``, ``'skip'``).
- Literals: numbers, ``'text'`` or ``"text"``, ``true``, ``false``, and lists
  ``['a', 'b']``.
- Comparisons: ``=`` (also ``==``), ``!=`` (also ``<>``), ``<``, ``>``, ``<=``, ``>=``.
- Logic: ``and`` (``&&``), ``or`` (``||``), ``not`` (``!``), and parentheses.
- Tests: ``{q} empty``, ``{q} notempty``, ``{q} contains 'x'``,
  ``{q} notcontains 'x'``, ``{q} anyof ['a', 'b']``.

Example::

    expr = parse_expression("{rating} < 3 and {why} notempty")
    expr.references            # {'rating', 'why'}
    expr.evaluate({"rating": 2, "why": "slow"})   # True
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_TOKEN = re.compile(
    r"""
    \s*(?:
      (?P<ref>\{[^{}]+\})
    | (?P<num>-?\d+(?:\.\d+)?)
    | (?P<str>'[^']*'|"[^"]*")
    | (?P<op><=|>=|==|!=|<>|&&|\|\||[=<>!()\[\],])
    | (?P<word>[A-Za-z_]+)
    )
    """,
    re.VERBOSE,
)

_COMPARISONS = {"=", "==", "!=", "<>", "<", ">", "<=", ">="}
_BINARY_WORDS = {"contains", "notcontains", "anyof"}
_POSTFIX_WORDS = {"empty", "notempty"}


class ExpressionError(ValueError):
    """An expression outside the grammar; the message says where."""


@dataclass(frozen=True)
class Expression:
    """A parsed condition. Evaluate it with :meth:`evaluate`."""

    source: str
    tree: tuple
    references: frozenset[str]

    def evaluate(self, values: Mapping[str, Any]) -> bool:
        """Return the condition's truth for ``values`` (question name → answer value)."""
        return _truthy(_eval(self.tree, values))


def parse_expression(source: str) -> Expression:
    """Parse ``source`` into an :class:`Expression`.

    Raises:
        ExpressionError: If ``source`` uses anything outside the grammar.
    """
    tokens = _tokenize(source)
    parser = _Parser(tokens, source)
    tree = parser.parse_or()
    leftover = parser.peek()
    if leftover is not None:
        raise ExpressionError(f"Unexpected {leftover[1]!r} in {source!r}.")
    return Expression(source=source, tree=tree, references=frozenset(_refs(tree)))


def _tokenize(source: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(source):
        if source[pos:].strip() == "":
            break
        match = _TOKEN.match(source, pos)
        if match is None or match.end() == pos:
            raise ExpressionError(f"Cannot read {source[pos:].strip()!r} in {source!r}.")
        kind = match.lastgroup
        assert kind is not None
        tokens.append((kind, match.group(kind)))
        pos = match.end()
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]], source: str) -> None:
        self._tokens = tokens
        self._pos = 0
        self._source = source

    def peek(self) -> tuple[str, str] | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _take(self) -> tuple[str, str]:
        token = self.peek()
        if token is None:
            raise ExpressionError(f"{self._source!r} ends too early.")
        self._pos += 1
        return token

    def _at(self, *texts: str) -> bool:
        token = self.peek()
        return token is not None and token[0] in ("op", "word") and token[1].lower() in texts

    def parse_or(self) -> tuple:
        left = self._parse_and()
        while self._at("or", "||"):
            self._take()
            left = ("or", left, self._parse_and())
        return left

    def _parse_and(self) -> tuple:
        left = self._parse_not()
        while self._at("and", "&&"):
            self._take()
            left = ("and", left, self._parse_not())
        return left

    def _parse_not(self) -> tuple:
        if self._at("not", "!"):
            self._take()
            return ("not", self._parse_not())
        return self._parse_test()

    def _parse_test(self) -> tuple:
        left = self._parse_operand()
        token = self.peek()
        if token is None:
            return left
        kind, text = token
        word = text.lower()
        if kind == "op" and text in _COMPARISONS:
            self._take()
            return ("cmp", text, left, self._parse_operand())
        if kind == "word" and word in _BINARY_WORDS:
            self._take()
            return (word, left, self._parse_operand())
        if kind == "word" and word in _POSTFIX_WORDS:
            self._take()
            return (word, left)
        return left

    def _parse_operand(self) -> tuple:
        kind, text = self._take()
        if kind == "ref":
            return ("ref", text[1:-1].strip())
        if kind == "num":
            return ("lit", float(text) if "." in text else int(text))
        if kind == "str":
            return ("lit", text[1:-1])
        if kind == "word" and text.lower() in ("true", "false"):
            return ("lit", text.lower() == "true")
        if kind == "op" and text == "(":
            inner = self.parse_or()
            if self._take() != ("op", ")"):
                raise ExpressionError(f"Missing ')' in {self._source!r}.")
            return inner
        if kind == "op" and text == "[":
            items: list[Any] = []
            while not self._at("]"):
                item = self._parse_operand()
                if item[0] != "lit":
                    raise ExpressionError(f"A list holds only literals, in {self._source!r}.")
                items.append(item[1])
                if self._at(","):
                    self._take()
                elif not self._at("]"):
                    raise ExpressionError(f"Expected ',' or ']' in {self._source!r}.")
            self._take()
            return ("lit", items)
        raise ExpressionError(
            f"Unexpected {text!r} in {self._source!r}: functions, arithmetic and piping are not supported."
        )


def _refs(tree: tuple) -> set[str]:
    if tree[0] == "ref":
        return {tree[1]}
    found: set[str] = set()
    for part in tree[1:]:
        if isinstance(part, tuple):
            found |= _refs(part)
    return found


def _eval(tree: tuple, values: Mapping[str, Any]) -> Any:
    op = tree[0]
    if op == "lit":
        return tree[1]
    if op == "ref":
        return values.get(tree[1])
    if op == "or":
        return _truthy(_eval(tree[1], values)) or _truthy(_eval(tree[2], values))
    if op == "and":
        return _truthy(_eval(tree[1], values)) and _truthy(_eval(tree[2], values))
    if op == "not":
        return not _truthy(_eval(tree[1], values))
    if op == "empty":
        return _is_empty(_eval(tree[1], values))
    if op == "notempty":
        return not _is_empty(_eval(tree[1], values))
    left = _eval(tree[2] if op == "cmp" else tree[1], values)
    right = _eval(tree[3] if op == "cmp" else tree[2], values)
    if op == "cmp":
        return _compare(tree[1], left, right)
    if op == "contains":
        return _contains(left, right)
    if op == "notcontains":
        return not _contains(left, right)
    if op == "anyof":
        wanted = right if isinstance(right, list) else [right]
        have = left if isinstance(left, list) else [left]
        return any(_equal(a, b) for a in have for b in wanted)
    raise ExpressionError(f"Unknown operation {op!r}.")


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or (isinstance(value, (list, dict)) and not value)


def _truthy(value: Any) -> bool:
    return not _is_empty(value) and value is not False and value != 0


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _equal(left: Any, right: Any) -> bool:
    a, b = _number(left), _number(right)
    if a is not None and b is not None:
        return a == b
    if isinstance(left, str) and isinstance(right, str):
        return left.lower() == right.lower()
    return bool(left == right)


def _compare(op: str, left: Any, right: Any) -> bool:
    if op in ("=", "=="):
        return _equal(left, right)
    if op in ("!=", "<>"):
        return not _equal(left, right)
    a, b = _number(left), _number(right)
    if a is None or b is None:
        return False
    return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]


def _contains(left: Any, right: Any) -> bool:
    if isinstance(left, list):
        return any(_equal(item, right) for item in left)
    if isinstance(left, str) and right is not None:
        return str(right).lower() in left.lower()
    return False

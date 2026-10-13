"""The macro a detached placement was made from."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MacroOrigin:
    """The macro template a Group's interior was copied from.

    Attributes:
        key: Registry key of the macro, e.g. ``"mylib:macro:Blur"``.
        hash: ``MacroTemplate.content_hash`` of the template at the time of the copy.
    """

    key: str
    hash: str

    def to_dict(self) -> dict[str, str]:
        """Return the origin as a JSON-serializable dict."""
        return {"key": self.key, "hash": self.hash}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "MacroOrigin":
        """Build an origin from the dict ``to_dict`` returns.

        Raises:
            KeyError: ``data`` has no ``key`` or no ``hash``.
        """
        return cls(key=str(data["key"]), hash=str(data["hash"]))

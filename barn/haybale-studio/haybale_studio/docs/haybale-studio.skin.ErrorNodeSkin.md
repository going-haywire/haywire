# Error

`haybale-studio:skin:ErrorNodeSkin` · kind: skin

Error skin that provides error styling for nodes

## Notes

Error skin that provides error styling for nodes.

This is the card a user stares at while diagnosing a broken node — either
one whose own skin raised, or one pinned to a skin that no longer resolves.
It lays ports out the way :class:`SplitNodeSkin` does (inlets and outlets in
columns, pinless configs full width beneath) so the shape is familiar, but
it renders through its own body rather than subclassing: a fallback that
inherits another skin's render path can be taken down by that skin's bugs,
which is the one thing this card must not do.

It ALWAYS shows everything — see :meth:`show_of`.

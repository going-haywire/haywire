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

It ALWAYS shows everything: ``render()`` never checks Node collapse at
all, and reads ``node.get_visible_ports()`` unconditionally rather than
the folded-card filter. Node collapse is a performance trade — draw fewer
ports on cards you are not reading. This is the card you ARE reading, and
the node behind it is already broken: hiding its ports to save elements
would withhold exactly the information the user opened it for. A node
folded to a title is a particularly bad failure mode here, since the fold
would hide the fact that anything is wrong.

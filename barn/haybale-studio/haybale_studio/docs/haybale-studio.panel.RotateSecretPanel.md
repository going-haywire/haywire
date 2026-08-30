# Sign everyone out

`haybale-studio:panel:RotateSecretPanel` · kind: panel

## Details

- **surface**: `account`
- **order**: `80`

## Notes

Rotates the cookie signing secret and evicts every live session.

The panic lever: one action that invalidates every issued cookie at once,
for when a laptop goes missing rather than when one principal leaves.

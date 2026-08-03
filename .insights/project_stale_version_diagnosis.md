# "Package X shows the old version" — where to look

A version the studio reports can come from three places that disagree with each
other, and the report never tells you which one you are looking at. Check them
in this order before touching code — it usually ends at step 1 or 2.

```sh
ls .venv/lib/python*/site-packages/ | grep <dist>   # what is ACTUALLY installed
grep <dist> pyproject.toml                          # the declared specifier
grep -A2 'name = "<dist>"' uv.lock                  # what the lock froze
```

**site-packages disagrees with the studio** → in-process metadata cache. The
studio imported that package at startup; `importlib.metadata.version()` can keep
answering with the version it saw then. `LibraryManager._invalidate_caches()`
clears it via `FastPath.__new__.cache_clear()`, a private CPython API wrapped in
`except AttributeError` — if that ever moves, the clear silently no-ops. Any
version destined for a *file* must be read off disk instead, because a stale
read there outlives the process as a pin.

**site-packages and lock agree, both behind a permissive specifier** → nothing
will move it. A specifier that admits the new version is not sufficient: if the
lock has already resolved it, `uv sync` honours the lock entry unless something
rewrites that dependency line. This is why a dist missing from an update's
rewrite set stays frozen indefinitely rather than drifting upward. Force it with:

```sh
uv lock --upgrade-package <dist> && uv sync   # studio stopped
```

**A `~=` on a haywire/haybale dist** → suspect a tool wrote it, not the author.
`~=0.0.z` excludes 0.1.0. Lockstep dists should carry `>=`; the three sites that
emit specifiers (`update.pin.rewrite_pins`, the marketplace write-back,
`dep_detect._format_specifier`) all normalize to floors deliberately. A ceiling
there is a regression, not a preference. Non-lockstep deps keep the author's
operator and are none of our business.

## Reading a traceback from an updated-in-place studio

Frames can point at code that no longer exists — line numbers, and even function
bodies, come from the modules the process imported *before* the update. Confirm
against the installed file before believing a frame; a mismatch means you are
reading the old version and the trace says nothing about current source.

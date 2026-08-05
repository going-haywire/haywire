"""Everything about a haybale library after it exists.

A haybale is created by ``haywire init`` (which lives outside this package —
it makes *projects*, not distributions). From then on, this package owns it:

* :mod:`~haywire_studio.packaging.share_cli` — the ``haywire share`` runner.
  The publishing *engine* it drives lives in :mod:`haywire.core.publishing`,
  not here: it imports nothing from ``haywire_studio``, and core already
  shells out to ``uv`` for the same class of workspace mutation
  (``haywire.core.update``).
* :mod:`~haywire_studio.packaging.docs` — deterministic README/OVERVIEW/
  QUICKREF generation (``haywire docs``).
* :mod:`~haywire_studio.packaging.rename` — rewrites a local library's
  identity across its package, decorator and graphs (``haywire rename``).
* :mod:`~haywire_studio.packaging.deps` — dependency-manifest drift audit
  (``haywire deps check``).

This package holds *domain logic only*. Argument parsing and process exit
codes belong to :mod:`haywire_studio.cli`, one module per subcommand.

Nothing here imports :mod:`haywire_studio.app` or any UI module; the whole
package must stay importable in a bare interpreter with no NiceGUI running,
because CI, the release automation and the test suite all drive it headless.
"""

from __future__ import annotations

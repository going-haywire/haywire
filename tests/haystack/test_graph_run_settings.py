"""GraphRunSettings — purely-local per-entry run policy bag."""

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_autorestart_defaults_false():
    from haybale_haystack.settings.graph_run_settings import GraphRunSettings

    s = GraphRunSettings()
    assert s.autorestart is False


def test_autorestart_can_be_set():
    from haybale_haystack.settings.graph_run_settings import GraphRunSettings

    s = GraphRunSettings()
    s.autorestart = True
    assert s.autorestart is True


def test_to_dict_is_sparse_when_default():
    """A bag at all-defaults serializes to an empty dict (sparse storage)."""
    from haybale_haystack.settings.graph_run_settings import GraphRunSettings

    s = GraphRunSettings()
    assert s.to_dict() == {}


def test_to_dict_emits_non_default():
    from haybale_haystack.settings.graph_run_settings import GraphRunSettings

    s = GraphRunSettings()
    s.autorestart = True
    assert s.to_dict() == {"autorestart": True}


def test_from_dict_restores_value():
    from haybale_haystack.settings.graph_run_settings import GraphRunSettings

    s = GraphRunSettings()
    s.from_dict({"autorestart": True})
    assert s.autorestart is True


def test_from_dict_ignores_unknown_keys():
    """Forward compatibility — unknown keys are silently ignored."""
    from haybale_haystack.settings.graph_run_settings import GraphRunSettings

    s = GraphRunSettings()
    s.from_dict({"autorestart": True, "future_flag": "x"})
    assert s.autorestart is True


def test_not_registry_backed():
    """Simple mode: no registry is injected (purely local)."""
    from haybale_haystack.settings.graph_run_settings import GraphRunSettings

    s = GraphRunSettings()
    assert s._registry is None

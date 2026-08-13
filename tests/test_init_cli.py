"""Tests for the `haywire init` CLI handler — argument validation, the
--distname override, and the confirm-before-scaffold prompt.

`init_project()` itself (the domain logic) is covered by
test_init_scaffolding.py; this file is scoped to what only cli/init.py owns:
argparse wiring, prompting, and exit codes.
"""

import argparse

import pytest


def _parse(argv: list[str]) -> argparse.Namespace:
    from haywire_studio.cli.init import register

    parser = argparse.ArgumentParser(prog="haywire")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers)
    return parser.parse_args(["init", *argv])


@pytest.fixture
def scaffold_dir(tmp_path, monkeypatch, fake_home):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Minimal version of test_init_scaffolding's fixture, scoped to what
    init_project() touches on the happy path."""
    fake = tmp_path / "fake-home"
    fake.mkdir()
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.setattr("pathlib.Path.home", lambda: fake)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Haywire Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@haywire.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Haywire Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@haywire.invalid")

    import haywire_studio.config as cfg

    fake_haywire = fake / ".haywire"
    monkeypatch.setattr(cfg, "GLOBAL_CONFIG_DIR", fake_haywire)

    import haybale_marketplace.config as mp_cfg

    global_mp_dir = fake_haywire / "db" / "haybale_marketplace"
    global_mp_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mp_cfg, "GLOBAL_MARKETPLACE_DIR", global_mp_dir)
    mp_cfg.ensure_marketplace_config()
    return fake


class TestArgParsing:
    def test_distname_defaults_to_none(self):
        args = _parse(["my-app"])
        assert args.distname is None

    def test_distname_captured(self):
        args = _parse(["my-app", "--distname", "acme-weather"])
        assert args.distname == "acme-weather"

    def test_yes_flag_defaults_false(self):
        args = _parse(["my-app"])
        assert args.yes is False

    def test_yes_flag_short_form(self):
        args = _parse(["my-app", "-y"])
        assert args.yes is True


class TestValidationExitsCleanly:
    """Invalid names are rejected before any prompt or scaffold, with a
    process exit code — not a raised exception bubbling out of _run."""

    def test_invalid_project_name_returns_nonzero(self, scaffold_dir, capsys):
        from haywire_studio.cli.init import _run

        args = _parse(["My Invalid Name", "--yes"])
        code = _run(args)
        assert code != 0
        assert "Error" in capsys.readouterr().out

    def test_invalid_distname_returns_nonzero(self, scaffold_dir, capsys):
        from haywire_studio.cli.init import _run

        args = _parse(["my-app", "--distname", "Not_Valid", "--yes"])
        code = _run(args)
        assert code != 0
        assert "Error" in capsys.readouterr().out

    def test_invalid_name_does_not_create_directory(self, scaffold_dir):
        from haywire_studio.cli.init import _run

        args = _parse(["My Invalid Name", "--yes"])
        _run(args)
        assert not (scaffold_dir / "My Invalid Name").exists()

    def test_uppercase_distname_rejected(self, scaffold_dir, capsys):
        """--distname stays strict — no case easing, unlike the project name."""
        from haywire_studio.cli.init import _run

        args = _parse(["my-app", "--distname", "Acme-Weather", "--yes"])
        code = _run(args)
        assert code != 0
        assert "Error" in capsys.readouterr().out


class TestUppercaseProjectNameAccepted:
    """Uppercase is allowed in the project name (eased gate); the scaffolded
    library identity is still lowercased."""

    def test_uppercase_project_name_scaffolds(self, scaffold_dir):
        from haywire_studio.cli.init import _run

        args = _parse(["My-App", "--yes", "--no-sync"])
        code = _run(args)
        assert code == 0
        assert (scaffold_dir / "My-App").is_dir()
        assert (scaffold_dir / "My-App" / "barn" / "hay-my-app").is_dir()


class TestYesSkipsPrompt:
    def test_yes_scaffolds_without_input(self, scaffold_dir, monkeypatch):
        from haywire_studio.cli.init import _run

        def _fail_if_called(_prompt=""):
            raise AssertionError("input() should not be called with --yes")

        monkeypatch.setattr("builtins.input", _fail_if_called)

        args = _parse(["my-app", "--yes", "--no-sync"])
        code = _run(args)
        assert code == 0
        assert (scaffold_dir / "my-app" / "barn" / "hay-my-app").is_dir()


class TestConfirmPrompt:
    def test_declining_aborts_without_scaffolding(self, scaffold_dir, monkeypatch):
        from haywire_studio.cli.init import _run

        monkeypatch.setattr("builtins.input", lambda _prompt="": "n")

        args = _parse(["my-app", "--no-sync"])
        code = _run(args)
        assert code != 0
        assert not (scaffold_dir / "my-app").exists()

    def test_accepting_scaffolds(self, scaffold_dir, monkeypatch):
        from haywire_studio.cli.init import _run

        monkeypatch.setattr("builtins.input", lambda _prompt="": "y")

        args = _parse(["my-app", "--no-sync"])
        code = _run(args)
        assert code == 0
        assert (scaffold_dir / "my-app" / "barn" / "hay-my-app").is_dir()

    def test_prompt_shows_resolved_distname(self, scaffold_dir, monkeypatch, capsys):
        from haywire_studio.cli.init import _run

        monkeypatch.setattr("builtins.input", lambda _prompt="": "n")

        args = _parse(["my-app", "--distname", "acme-weather", "--no-sync"])
        _run(args)
        out = capsys.readouterr().out
        assert "acme-weather" in out
        assert "acme_weather" in out


class TestDistnamePassthrough:
    def test_distname_flows_through_to_scaffold(self, scaffold_dir, monkeypatch):
        from haywire_studio.cli.init import _run

        monkeypatch.setattr("builtins.input", lambda _prompt="": "y")

        args = _parse(["my-app", "--distname", "acme-weather", "--no-sync"])
        code = _run(args)
        assert code == 0
        assert (scaffold_dir / "my-app" / "barn" / "acme-weather").is_dir()
        assert not (scaffold_dir / "my-app" / "barn" / "hay-my-app").exists()

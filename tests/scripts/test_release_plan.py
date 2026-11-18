"""scripts/release_plan.py: what a run of publish.yml does for each kind of push."""

from __future__ import annotations

import pytest

from scripts import release_plan as plan

pytestmark = pytest.mark.unit

TAGS = ["v0.5.2", "v0.5.10", "v0.5.9", "marketstall-latest"]


def decide(version="0.5.11", tags=TAGS, *, event="push", ref="refs/heads/master", ref_type="branch"):
    ref_name = ref.rsplit("/", 1)[-1]
    return plan.decide(event, ref, ref_type, ref_name, "master", version, tags)


def test_a_push_to_master_with_a_new_version_releases_and_creates_the_tag():
    result = decide("0.5.11")
    assert (result.release, result.version, result.tag) == (True, "0.5.11", "v0.5.11")


def test_a_push_to_master_at_the_latest_tag_is_no_release():
    assert not decide("0.5.10").release


def test_the_latest_tag_is_the_highest_number_not_the_last_string():
    assert plan.latest_release(TAGS) == "v0.5.10"
    assert plan.latest_release(["nightly"]) is None


def test_a_version_tagged_earlier_but_not_the_latest_is_refused():
    with pytest.raises(plan.PlanError, match="tagged but is not the latest"):
        decide("0.5.9")


def test_a_manual_tag_push_publishes_that_tag_and_creates_nothing():
    result = decide(ref="refs/tags/v0.6.0", ref_type="tag")
    assert (result.release, result.version, result.tag) == (True, "0.6.0", "")


def test_a_pushed_tag_that_is_not_a_release_is_refused():
    with pytest.raises(plan.PlanError):
        decide(ref="refs/tags/v0.6", ref_type="tag")


def test_a_push_to_another_branch_is_no_release():
    assert not decide("0.5.11", ref="refs/heads/feat/x").release


def test_a_dispatch_releases_the_tree_version_and_tags_only_a_missing_tag():
    missing = decide("0.5.11", event="workflow_dispatch")
    existing = decide("0.5.10", event="workflow_dispatch")
    assert (missing.release, missing.tag) == (True, "v0.5.11")
    assert (existing.release, existing.tag) == (True, "")


def test_a_malformed_tree_version_is_refused():
    with pytest.raises(plan.PlanError):
        decide("0.5")


def test_main_reads_the_tree_and_writes_the_outputs(monkeypatch, tmp_path):
    (tmp_path / "packages/haywire-core").mkdir(parents=True)
    (tmp_path / "packages/haywire-core/pyproject.toml").write_text(
        '[project]\nname = "haywire-core"\nversion = "0.5.11"\n'
    )
    out = tmp_path / "output"
    monkeypatch.chdir(tmp_path)
    for name, value in {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF": "refs/heads/master",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "master",
        "DEFAULT_BRANCH": "master",
        "GITHUB_OUTPUT": str(out),
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(plan.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "v0.5.10\n"})())

    assert plan.main() == 0
    assert out.read_text() == "release=true\nversion=0.5.11\ntag=v0.5.11\n"

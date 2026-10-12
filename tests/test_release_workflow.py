"""Static checks for the release artefacts (M7).

These tests don't actually run a release. They ensure the YAML workflow
files are syntactically valid and that the release workflow cannot
accidentally run on a pull request.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


@pytest.mark.skipif(yaml is None, reason="PyYAML not installed")
def test_release_workflow_is_valid_yaml() -> None:
    path = WORKFLOWS_DIR / "release.yml"
    assert path.exists(), f"{path} missing"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "jobs" in data
    assert "publish" in data["jobs"]


@pytest.mark.skipif(yaml is None, reason="PyYAML not installed")
def test_release_workflow_only_triggers_on_tag_push() -> None:
    path = WORKFLOWS_DIR / "release.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    triggers = data.get(True, data.get("on", {}))  # PyYAML quirk: 'on' -> True
    assert "pull_request" not in triggers, "release.yml must not trigger on pull_request"
    push = triggers.get("push", {})
    if isinstance(push, dict):
        tags = push.get("tags", [])
        # tags is a list of patterns; we want a v* pattern
        assert any("v*" in str(t) for t in tags), (
            "release.yml push trigger should match tag pattern v*"
        )


@pytest.mark.skipif(yaml is None, reason="PyYAML not installed")
def test_release_workflow_publish_uses_trusted_publisher() -> None:
    """The publish job should use ``pypa/gh-action-pypi-publish`` with no
    explicit credentials, relying on the ``id-token: write`` permission
    and the GitHub ``pypi`` environment."""
    path = WORKFLOWS_DIR / "release.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    publish = data["jobs"]["publish"]
    # environment is set
    assert publish.get("environment", {}).get("name") == "pypi"
    # permissions: id-token must be write
    assert publish.get("permissions", {}).get("id-token") == "write"
    # step uses pypa/gh-action-pypi-publish
    text = path.read_text(encoding="utf-8")
    assert "pypa/gh-action-pypi-publish" in text


@pytest.mark.skipif(yaml is None, reason="PyYAML not installed")
def test_pages_workflow_is_valid_yaml() -> None:
    path = WORKFLOWS_DIR / "pages.yml"
    assert path.exists(), f"{path} missing"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "jobs" in data


@pytest.mark.skipif(yaml is None, reason="PyYAML not installed")
def test_ci_workflow_is_valid_yaml() -> None:
    path = WORKFLOWS_DIR / "ci.yml"
    assert path.exists(), f"{path} missing"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "jobs" in data
    assert "test" in data["jobs"]


def test_changelog_exists() -> None:
    p = REPO_ROOT / "CHANGELOG.md"
    assert p.exists()
    assert "Changelog" in p.read_text(encoding="utf-8")


def test_license_exists() -> None:
    p = REPO_ROOT / "LICENSE"
    assert p.exists()
    assert "MIT" in p.read_text(encoding="utf-8")


def test_releasing_md_exists() -> None:
    p = REPO_ROOT / "RELEASING.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "pypi" in text.lower()
    assert "trusted" in text.lower()

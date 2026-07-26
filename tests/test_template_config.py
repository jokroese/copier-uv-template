from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_root_is_non_package_tooling_project() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "package = false" in pyproject
    assert "[build-system]" not in pyproject
    assert not (ROOT / "src" / "smoke_library").exists()


def test_copier_min_version_and_cli_kind() -> None:
    data = yaml.safe_load((ROOT / "copier.yml").read_text(encoding="utf-8"))
    assert data["_min_copier_version"] == "9.17.0"
    assert data["project_kind"]["choices"] == ["cli", "library"]
    assert data["project_kind"]["default"] == "cli"


def test_uv_is_exactly_pinned() -> None:
    assert (ROOT / "uv.toml").read_text(encoding="utf-8").strip() == (
        'required-version = "==0.11.32"'
    )
    precommit = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "rev: 0.11.32" in precommit


def test_uv_lock_is_skipped_on_update() -> None:
    data = yaml.safe_load((ROOT / "copier.yml").read_text(encoding="utf-8"))
    assert "uv.lock" in data["_skip_if_exists"]

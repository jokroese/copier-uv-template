from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.dogfood


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def _assert_no_jinja_placeholders(project_dir: Path) -> None:
    # Fail if template markers leak into output.
    bad = []
    for path in project_dir.rglob("*"):
        if path.is_file() and path.suffix not in {".png", ".jpg", ".jpeg", ".gif"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "{{" in text or "{%" in text:
                bad.append(str(path.relative_to(project_dir)))
    assert not bad, f"Jinja placeholders leaked into output: {bad}"


def _git_diff_is_clean(project_dir: Path) -> bool:
    p = subprocess.run(["git", "diff", "--exit-code"], cwd=project_dir)
    return p.returncode == 0


def _assert_generated_repo_pins_uv(project_dir: Path) -> None:
    uv_toml = project_dir / "uv.toml"
    assert uv_toml.is_file(), "Generated repo must contain uv.toml"
    text = uv_toml.read_text(encoding="utf-8")
    assert "required-version" in text, "uv.toml must set required-version"


def test_generate_app_project_and_run_quality(copie) -> None:
    result = copie.copy(
        extra_answers={
            "project_name": "Dogfood App",
            "project_slug": "dogfood-app",
            "package_name": "dogfood_app",
            "description": "Dogfood generated app",
            "python_version": "3.12",
            "project_kind": "app",
            "use_precommit": True,
        }
    )
    assert result.exit_code == 0
    project_dir: Path = result.project_dir

    assert (project_dir / "src" / "dogfood_app").is_dir()
    assert (project_dir / ".github" / "workflows" / "ci.yml").is_file()
    _assert_generated_repo_pins_uv(project_dir)

    _assert_no_jinja_placeholders(project_dir)

    # Lock twice; ensure stable resolution.
    _run(["uv", "lock"], cwd=project_dir)
    _run(["git", "init"], cwd=project_dir)
    _run(["git", "config", "init.defaultBranch", "main"], cwd=project_dir)
    _run(["git", "config", "user.email", "ci@example.invalid"], cwd=project_dir)
    _run(["git", "config", "user.name", "CI"], cwd=project_dir)
    _run(["git", "add", "-A"], cwd=project_dir)
    _run(["git", "commit", "-m", "init"], cwd=project_dir)
    _run(["uv", "lock"], cwd=project_dir)
    assert _git_diff_is_clean(project_dir), (
        "uv.lock changed on second lock; resolution is not stable"
    )

    _run(["uv", "sync", "--dev"], cwd=project_dir)

    _run(["uv", "run", "ruff", "check", "."], cwd=project_dir)
    _run(["uv", "run", "ruff", "format", "--check", "."], cwd=project_dir)
    _run(["uv", "run", "pyright"], cwd=project_dir)
    _run(["uv", "run", "pytest"], cwd=project_dir)

    _run(["uv", "run", "pre-commit", "run", "-a"], cwd=project_dir)


def test_generate_library_project_and_build(copie) -> None:
    result = copie.copy(
        extra_answers={
            "project_name": "Dogfood Lib",
            "project_slug": "dogfood-lib",
            "package_name": "dogfood_lib",
            "description": "Dogfood generated library",
            "python_version": "3.12",
            "project_kind": "library",
            "use_precommit": True,
        }
    )
    assert result.exit_code == 0
    project_dir: Path = result.project_dir

    assert (project_dir / "src" / "dogfood_lib").is_dir()
    assert (project_dir / ".github" / "workflows" / "ci.yml").is_file()
    _assert_generated_repo_pins_uv(project_dir)

    _assert_no_jinja_placeholders(project_dir)

    _run(["uv", "lock"], cwd=project_dir)
    _run(["git", "init"], cwd=project_dir)
    _run(["git", "config", "init.defaultBranch", "main"], cwd=project_dir)
    _run(["git", "config", "user.email", "ci@example.invalid"], cwd=project_dir)
    _run(["git", "config", "user.name", "CI"], cwd=project_dir)
    _run(["git", "add", "-A"], cwd=project_dir)
    _run(["git", "commit", "-m", "init"], cwd=project_dir)
    _run(["uv", "lock"], cwd=project_dir)
    assert _git_diff_is_clean(project_dir), (
        "uv.lock changed on second lock; resolution is not stable"
    )

    _run(["uv", "sync", "--dev"], cwd=project_dir)

    _run(["uv", "run", "ruff", "check", "."], cwd=project_dir)
    _run(["uv", "run", "ruff", "format", "--check", "."], cwd=project_dir)
    _run(["uv", "run", "pyright"], cwd=project_dir)
    _run(["uv", "run", "pytest"], cwd=project_dir)

    _run(["uv", "run", "pre-commit", "run", "-a"], cwd=project_dir)

    # Library-only contract: build must succeed.
    _run(["uv", "build"], cwd=project_dir)

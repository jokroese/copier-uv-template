from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.dogfood

_TIMEOUT = 120


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
        timeout=_TIMEOUT,
    )


def _assert_no_jinja_placeholders(project_dir: Path) -> None:
    # Fail if template markers leak into output.
    bad = []
    for path in project_dir.rglob("*"):
        if path.is_file() and path.suffix not in {".png", ".jpg", ".jpeg", ".gif"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            # Ignore GitHub Actions expressions like ${{ github.ref }}.
            text = re.sub(r"\$\{\{.*?\}\}", "", text, flags=re.DOTALL)
            if "{{" in text or "{%" in text:
                bad.append(str(path.relative_to(project_dir)))
    assert not bad, f"Jinja placeholders leaked into output: {bad}"


def _git_diff_is_clean(project_dir: Path) -> bool:
    p = subprocess.run(
        ["git", "diff", "--exit-code"],
        cwd=project_dir,
        timeout=_TIMEOUT,
    )
    return p.returncode == 0


def _assert_generated_repo_pins_uv(project_dir: Path) -> None:
    uv_toml = project_dir / "uv.toml"
    assert uv_toml.is_file(), "Generated repo must contain uv.toml"
    text = uv_toml.read_text(encoding="utf-8")
    assert 'required-version = "==' in text, "uv.toml must set exact required-version"


def _init_git(project_dir: Path) -> None:
    _run(["git", "init", "-b", "main"], cwd=project_dir)
    _run(["git", "config", "user.email", "ci@example.invalid"], cwd=project_dir)
    _run(["git", "config", "user.name", "CI"], cwd=project_dir)
    _run(["git", "add", "-A"], cwd=project_dir)
    _run(["git", "commit", "-m", "init"], cwd=project_dir)


def test_generate_cli_project_and_run_quality(copie) -> None:
    result = copie.copy(
        extra_answers={
            "project_name": "Dogfood Cli",
            "project_slug": "dogfood-cli",
            "package_name": "dogfood_cli",
            "description": "Dogfood generated cli",
            "python_version": "3.12",
            "project_kind": "cli",
            "use_precommit": True,
        }
    )
    assert result.exit_code == 0
    project_dir: Path = result.project_dir

    package_dir = project_dir / "src" / "dogfood_cli"
    assert package_dir.is_dir()
    assert (package_dir / "cli.py").is_file()
    assert (package_dir / "__main__.py").is_file()
    assert (project_dir / ".github" / "workflows" / "ci.yml").is_file()
    pyproject = (project_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert "dogfood_cli.cli:main" in pyproject
    _assert_generated_repo_pins_uv(project_dir)

    _assert_no_jinja_placeholders(project_dir)

    # Lock twice; ensure stable resolution.
    _run(["uv", "lock"], cwd=project_dir)
    _init_git(project_dir)
    _run(["uv", "lock"], cwd=project_dir)
    assert _git_diff_is_clean(project_dir), (
        "uv.lock changed on second lock; resolution is not stable"
    )

    _run(["uv", "sync", "--dev"], cwd=project_dir)

    _run(["uv", "run", "ruff", "check", "."], cwd=project_dir)
    _run(["uv", "run", "ruff", "format", "--check", "."], cwd=project_dir)
    _run(["uv", "run", "pyright"], cwd=project_dir)
    _run(["uv", "run", "pytest"], cwd=project_dir)

    script = _run(["uv", "run", "dogfood-cli"], cwd=project_dir)
    assert "Hello from dogfood-cli" in script.stdout
    module = _run(
        ["uv", "run", "python", "-m", "dogfood_cli"],
        cwd=project_dir,
    )
    assert "Hello from dogfood-cli" in module.stdout

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

    package_dir = project_dir / "src" / "dogfood_lib"
    assert package_dir.is_dir()
    assert not (package_dir / "cli.py").exists()
    assert not (package_dir / "__main__.py").exists()
    assert (project_dir / ".github" / "workflows" / "ci.yml").is_file()
    pyproject = (project_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.scripts]" not in pyproject
    _assert_generated_repo_pins_uv(project_dir)

    _assert_no_jinja_placeholders(project_dir)

    _run(["uv", "lock"], cwd=project_dir)
    _init_git(project_dir)
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


def test_use_precommit_false_omits_config_and_dependency(copie) -> None:
    result = copie.copy(
        extra_answers={
            "project_name": "No Precommit",
            "project_slug": "no-precommit",
            "package_name": "no_precommit",
            "description": "Generated without pre-commit",
            "python_version": "3.12",
            "project_kind": "cli",
            "use_precommit": False,
        }
    )
    assert result.exit_code == 0
    project_dir: Path = result.project_dir

    assert not (project_dir / ".pre-commit-config.yaml").exists()
    pyproject = (project_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert "pre-commit" not in pyproject

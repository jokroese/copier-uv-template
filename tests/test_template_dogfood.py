from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml
from copier.errors import CopierAnswersInterrupt

pytestmark = pytest.mark.dogfood

_TIMEOUT = 180
_TEMPLATE = Path(__file__).resolve().parents[1]


def _run(
    cmd: list[str],
    cwd: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=True,
        timeout=_TIMEOUT,
    )


def _assert_no_jinja_placeholders(project_dir: Path) -> None:
    bad = []
    for path in project_dir.rglob("*"):
        if path.is_file() and path.suffix not in {".png", ".jpg", ".jpeg", ".gif"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
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


def _lock_and_sync(project_dir: Path) -> None:
    _run(["uv", "lock"], cwd=project_dir)
    _init_git(project_dir)
    _run(["uv", "lock"], cwd=project_dir)
    assert _git_diff_is_clean(project_dir), (
        "uv.lock changed on second lock; resolution is not stable"
    )
    _run(["uv", "sync", "--dev"], cwd=project_dir)


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

    _lock_and_sync(project_dir)

    _run(["uv", "run", "ruff", "check", "."], cwd=project_dir)
    _run(["uv", "run", "ruff", "format", "--check", "."], cwd=project_dir)
    _run(["uv", "run", "pyright"], cwd=project_dir)
    _run(["uv", "run", "pytest"], cwd=project_dir)

    script = _run(["uv", "run", "dogfood-cli"], cwd=project_dir)
    assert "Hello from dogfood-cli" in script.stdout
    module = _run(["uv", "run", "python", "-m", "dogfood_cli"], cwd=project_dir)
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
    assert (package_dir / "py.typed").is_file()
    assert (project_dir / ".github" / "workflows" / "ci.yml").is_file()
    pyproject = (project_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.scripts]" not in pyproject
    _assert_generated_repo_pins_uv(project_dir)
    _assert_no_jinja_placeholders(project_dir)

    _lock_and_sync(project_dir)

    _run(["uv", "run", "ruff", "check", "."], cwd=project_dir)
    _run(["uv", "run", "ruff", "format", "--check", "."], cwd=project_dir)
    _run(["uv", "run", "pyright"], cwd=project_dir)
    _run(["uv", "run", "pytest"], cwd=project_dir)
    _run(["uv", "run", "pre-commit", "run", "-a"], cwd=project_dir)

    _run(["uv", "build"], cwd=project_dir)
    dist = project_dir / "dist"
    wheels = list(dist.glob("*.whl"))
    sdists = list(dist.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1

    for artifact in (wheels[0], sdists[0]):
        probe = _run(
            [
                "uv",
                "run",
                "--isolated",
                "--no-project",
                "--with",
                str(artifact),
                "python",
                "-c",
                (
                    "import dogfood_lib, importlib.resources as r; "
                    "assert dogfood_lib.__all__ == []; "
                    "assert (r.files('dogfood_lib') / 'py.typed').is_file()"
                ),
            ],
            cwd=project_dir,
        )
        assert probe.returncode == 0


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
    data = tomllib.loads((project_dir / "pyproject.toml").read_text(encoding="utf-8"))
    assert "pre-commit" not in data.get("dependency-groups", {}).get("dev", [])


def test_description_with_quotes_produces_valid_toml(copie) -> None:
    result = copie.copy(
        extra_answers={
            "project_name": "Quoted Desc",
            "project_slug": "quoted-desc",
            "package_name": "quoted_desc",
            "description": 'Say "hello"\nand goodbye',
            "python_version": "3.12",
            "project_kind": "library",
            "use_precommit": False,
        }
    )
    assert result.exit_code == 0
    project_dir: Path = result.project_dir
    data = tomllib.loads((project_dir / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["description"] == 'Say "hello"\nand goodbye'


def test_python_314_generation_locks(copie) -> None:
    result = copie.copy(
        extra_answers={
            "project_name": "Py314",
            "project_slug": "py314",
            "package_name": "py314",
            "description": "Python 3.14 generation",
            "python_version": "3.14",
            "project_kind": "library",
            "use_precommit": False,
        }
    )
    assert result.exit_code == 0
    project_dir: Path = result.project_dir
    assert (project_dir / ".python-version").read_text(
        encoding="utf-8"
    ).strip() == "3.14"
    _run(["uv", "lock"], cwd=project_dir)
    assert (project_dir / "uv.lock").is_file()


@pytest.mark.parametrize(
    ("answers", "fragment"),
    [
        (
            {
                "project_name": "Bad",
                "project_slug": "Bad_Slug",
                "package_name": "bad_slug",
                "description": "",
                "python_version": "3.12",
                "project_kind": "cli",
                "use_precommit": False,
            },
            "slug",
        ),
        (
            {
                "project_name": "Bad",
                "project_slug": "bad-slug",
                "package_name": "class",
                "description": "",
                "python_version": "3.12",
                "project_kind": "cli",
                "use_precommit": False,
            },
            "keyword",
        ),
        (
            {
                "project_name": "Bad",
                "project_slug": "bad-slug",
                "package_name": "bad_slug",
                "description": "",
                "python_version": "3.12.1",
                "project_kind": "cli",
                "use_precommit": False,
            },
            "MAJOR.MINOR",
        ),
    ],
)
def test_invalid_answers_are_rejected(
    copie, answers: dict[str, object], fragment: str
) -> None:
    result = copie.copy(extra_answers=answers)
    assert result.exit_code != 0
    combined = f"{result.exception}\n{getattr(result, 'output', '')}".lower()
    assert fragment.lower() in combined or isinstance(
        result.exception,
        (SystemExit, ValueError, CopierAnswersInterrupt),
    )


def test_copier_update_preserves_user_file_and_lock(copie) -> None:
    result = copie.copy(
        extra_answers={
            "project_name": "Update Me",
            "project_slug": "update-me",
            "package_name": "update_me",
            "description": "Update dogfood",
            "python_version": "3.12",
            "project_kind": "library",
            "use_precommit": False,
        }
    )
    assert result.exit_code == 0
    project_dir: Path = result.project_dir

    _run(["uv", "lock"], cwd=project_dir)
    _init_git(project_dir)

    commit = _run(["git", "rev-parse", "HEAD"], cwd=_TEMPLATE).stdout.strip()
    answers_path = project_dir / ".copier-answers.yml"
    answers_path.write_text(
        yaml.safe_dump(
            {
                "_src_path": str(_TEMPLATE),
                "_commit": commit,
                "project_name": "Update Me",
                "project_slug": "update-me",
                "package_name": "update_me",
                "description": "Update dogfood",
                "python_version": "3.12",
                "project_kind": "library",
                "use_precommit": False,
            }
        ),
        encoding="utf-8",
    )
    user_file = project_dir / "USER_NOTE.md"
    user_file.write_text("keep me\n", encoding="utf-8")
    _run(["git", "add", "-A"], cwd=project_dir)
    _run(["git", "commit", "-m", "add answers and user file"], cwd=project_dir)

    lock_before = (project_dir / "uv.lock").read_text(encoding="utf-8")

    update = _run(
        [
            "uv",
            "run",
            "copier",
            "update",
            "--defaults",
            "--skip-answered",
            "--trust",
            f"--vcs-ref={commit}",
            str(project_dir),
        ],
        cwd=_TEMPLATE,
        check=False,
    )
    assert update.returncode == 0, f"stdout={update.stdout}\nstderr={update.stderr}"
    assert user_file.read_text(encoding="utf-8") == "keep me\n"
    assert (project_dir / "uv.lock").read_text(encoding="utf-8") == lock_before

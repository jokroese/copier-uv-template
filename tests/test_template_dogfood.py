from __future__ import annotations

import re
import subprocess
from pathlib import Path


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


def _parse_version(s: str) -> tuple[int, ...]:
    return tuple(int(x) for x in s.strip().split("."))


def _assert_uv_version_in_range(project_dir: Path) -> None:
    """Assert generated repo pins uv and current uv satisfies it."""
    uv_toml = project_dir / "uv.toml"
    assert uv_toml.is_file(), (
        "Generated repo must contain uv.toml for setup-uv to pin version"
    )
    text = uv_toml.read_text()
    m = re.search(r'required-version\s*=\s*">=([^,]+),<([^"]+)"', text)
    assert m, f'uv.toml must define required-version = ">=X,<Y"; got: {text!r}'
    min_ver_str, max_ver_str = m.group(1).strip(), m.group(2).strip()
    min_ver = _parse_version(min_ver_str)
    max_ver = _parse_version(max_ver_str)

    result = subprocess.run(
        ["uv", "--version"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout or result.stderr
    ver_m = re.search(r"(\d+\.\d+(?:\.\d+)?)", out)
    assert ver_m, f"Cannot parse uv version from: {out!r}"
    current = _parse_version(ver_m.group(1))

    assert min_ver <= current < max_ver, (
        f"uv --version {ver_m.group(1)} must be >= {min_ver_str} and < {max_ver_str} "
        f"(from {uv_toml})"
    )


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
    _assert_uv_version_in_range(project_dir)

    _assert_no_jinja_placeholders(project_dir)

    # Lock twice; ensure stable resolution.
    _run(["uv", "lock"], cwd=project_dir)
    _run(["git", "init"], cwd=project_dir)
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
    _assert_uv_version_in_range(project_dir)

    _assert_no_jinja_placeholders(project_dir)

    _run(["uv", "lock"], cwd=project_dir)
    _run(["git", "init"], cwd=project_dir)
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

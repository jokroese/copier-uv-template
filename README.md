# copier-uv-template

A lean Copier template for modern Python projects using uv (packaged CLIs and libraries), with CI, Ruff, Pyright, pytest, and optional pre-commit.

## Use

```bash
uvx --from "copier>=9.17.0" copier copy gh:jokroese/copier-uv-template my-new-repo
cd my-new-repo
git init -b main
uv sync --dev
uv run pytest
```

## What you get

- `cli` (default): src layout, `cli.py`, `python -m package`, and a console script
- `library`: src layout with `py.typed`, no CLI entrypoints; CI runs `uv build`
- GitHub Actions CI: lint, format check, type check, tests
- Ruff + Pyright + pytest wired via `uv run`
- Optional pre-commit (when enabled): config file, `pre-commit` dependency, and uv-lock hook

## Updating a generated project

```bash
copier update
uv lock
uv sync --dev
```

`uv.lock` is listed in `_skip_if_exists`, so Copier will not refresh it. Always run `uv lock` after an update and commit the result.

Projects generated before `v0.2.0` with `project_kind: app` are migrated to `cli` on update.

## Working on this template

```bash
uv sync --group dev --group dogfood
uv run pytest
```

This repo pins uv exactly (`required-version = "==0.11.32"`). The same version is used for pre-commit’s `uv-pre-commit` rev and the template’s internal `uv_version`.

Bump every pin together:

```bash
./scripts/bump-uv.sh 0.11.32
uv lock
```

Renovate is configured to group GitHub Actions SHA updates and keep the uv pin sites in sync.

# copier-uv-template

A lean Copier template for modern Python projects using uv (apps and libraries), with CI, Ruff, Pyright, pytest, and optional pre-commit.

## Use

```bash
uvx copier copy gh:jokroese/copier-uv-template my-new-repo
cd my-new-repo
uv sync --dev
uv run pytest
```

## What you get

- src/ layout with py.typed
- GitHub Actions CI: lint, format check, type check, tests (and uv build for libraries)
- Ruff + Pyright + pytest wired via uv run
- Optional pre-commit, including an uv-lock hook

## Working on this template

Run the contract tests that generate app + library repos and execute the full toolchain:

```bash
uv sync --group dev --group dogfood
uv run pytest
```

## Updating dependencies

```bash
uv lock --upgrade
uv sync --dev
```

CI uses `uv sync --locked`; commit uv.lock after changes.

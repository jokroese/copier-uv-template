# copier-uv-template

Copier template for Python repos using `uv`, `ruff`, `pyright`, `pytest`, `pre-commit`, and a thin GitHub Actions workflow.

## Use

```bash
uvx copier copy --trust path/to/copier-uv-template path/to/new-repo
cd path/to/new-repo
uv sync --dev
```

# Validate a generated repo

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

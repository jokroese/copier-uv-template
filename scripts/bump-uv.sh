#!/usr/bin/env bash
# Bump the exact uv pin in every template and root location.
set -euo pipefail

DEFAULT_UV_VERSION="0.11.32"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-}"

if [[ -z "$VERSION" ]]; then
  echo "usage: $0 <uv-version>" >&2
  echo "example: $0 ${DEFAULT_UV_VERSION}" >&2
  exit 2
fi

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "invalid uv version: $VERSION (expected MAJOR.MINOR.PATCH)" >&2
  exit 2
fi

python - "$ROOT" "$VERSION" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
version = sys.argv[2]

replacements: list[tuple[Path, re.Pattern[str], str]] = [
    (
        root / "copier.yml",
        re.compile(r'(default: ")(\d+\.\d+\.\d+)("\s*\n\s*when: false)'),
        rf"\g<1>{version}\g<3>",
    ),
    (
        root / "uv.toml",
        re.compile(r'(required-version = "==)\d+\.\d+\.\d+(")'),
        rf"\g<1>{version}\g<2>",
    ),
    (
        root / "pyproject.toml",
        re.compile(r"(uv_build==)\d+\.\d+\.\d+"),
        rf"\g<1>{version}",
    ),
    (
        root / ".pre-commit-config.yaml",
        re.compile(r"(rev: )\d+\.\d+\.\d+"),
        rf"\g<1>{version}",
    ),
    (
        root / "scripts" / "bump-uv.sh",
        re.compile(r'(DEFAULT_UV_VERSION=")\d+\.\d+\.\d+(")'),
        rf"\g<1>{version}\g<2>",
    ),
]

# Template files derive from uv_version / keep exact pin via =={{ uv_version }}.
# Root pyproject no longer has uv_build after non-package conversion — skip if absent.

for path, pattern, repl in replacements:
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8")
    updated, n = pattern.subn(repl, text, count=1)
    if n == 0 and path.name != "pyproject.toml":
        raise SystemExit(f"no pin matched in {path}")
    if n:
        path.write_text(updated, encoding="utf-8")
        print(f"updated {path.relative_to(root)}")

print(f"uv pin set to {version}")
print("next: uv lock && git add -A && git commit")
PY

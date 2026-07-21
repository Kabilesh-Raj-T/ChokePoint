# CI Validation Report

This report documents the DevOps review for fresh GitHub runner readiness.

## Runner Matrix

CI validates the project on:

- Ubuntu latest
- Windows latest
- macOS latest
- Python 3.12
- Python 3.13

The workflow explicitly passes the matrix Python version to `uv sync` so the
repository-level `.python-version` does not accidentally force all jobs onto
Python 3.12.

## Fixed

- Expanded CI from Ubuntu-only to Ubuntu, Windows, and macOS.
- Kept Python coverage for both 3.12 and 3.13.
- Enabled uv dependency caching using `uv.lock`.
- Replaced platform-specific virtualenv activation in GitHub Actions with a
  Python smoke-test script.
- Added editable-install validation with `pip install -e .`.
- Added wheel and sdist install validation.
- Verified both `python -m blastradius` and the `blastradius` console script.
- Updated pre-commit to use local `uv run` hooks so mypy sees the same project
  dependencies as CI.
- Included `scripts/` in Black, Ruff, and mypy validation.
- Fixed `src/blastradius/py.typed` end-of-file hygiene.
- Ignored `.wheel-smoke/` local smoke-test leftovers.

## Local Validation

The following checks passed locally:

```text
uv sync --frozen --python 3.12
uv run pre-commit run --all-files
uv run black --check src tests scripts
uv run ruff check src tests scripts
uv run mypy
uv run pytest -q
uv build
uv run python scripts/smoke_install.py --editable
uv run python scripts/smoke_install.py --wheel --sdist
```

## Package Validation

The smoke installer creates an isolated temporary virtual environment and
verifies:

- editable install
- wheel install
- sdist install
- `python -m blastradius validate examples/basic.yaml`
- `blastradius --help`

## Release Workflow

The release workflow now mirrors the quality gate, builds distributions, and
smoke-tests both built artifacts before uploading them.

## Remaining Notes

- CI is expected to be slower because it now performs a full 3 OS x 2 Python
  matrix and isolated install smoke tests.
- Release builds remain single-platform on Ubuntu/Python 3.12 because Python
  wheels are pure Python and CI already validates runtime behavior across the
  full platform matrix.

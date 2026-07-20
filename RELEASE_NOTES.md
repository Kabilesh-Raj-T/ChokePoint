# ChokePoint 1.0.0 Project Notes

Release date: 2026-07-19

ChokePoint 1.0.0 is a portfolio milestone for the infrastructure dependency
graph analyzer. It provides a typed Python API and CLI for ingesting
infrastructure descriptions, constructing dependency graphs, identifying choke
points, and exporting reports for engineering review.

## Highlights

- Python 3.12+ package using `uv`, `pyproject.toml`, and a `src/` layout.
- Typed topology model for nodes, edges, and dependency relationships.
- YAML topology parser with helpful validation errors.
- Basic Terraform HCL and Docker Compose parsers.
- NetworkX-backed graph analysis for articulation points, bridges, components,
  centrality, cycles, and validation.
- Risk engine for shared DNS, identity, CDN, secrets, monitoring, networking,
  CI/CD, email, and single-service articulation risks.
- CLI commands for `analyze`, `graph`, `report`, `validate`, `export`, and
  `diff`.
- Core exports for Markdown, JSON, terminal, CSV, and Mermaid.

## Notes

The richer experimental version with additional parsers and exports is preserved
on the `advanced` branch. The `main` branch stays focused on the core graph
analysis project.

## Verification

The project checks passed:

```text
uv run black src tests
uv run ruff check src tests
uv run mypy
uv run pytest
uv build
pip install -e .
pip install dist/chokepoint-1.0.0-py3-none-any.whl
```

Coverage is enforced at 95% or higher. CI also smoke-installs the built wheel
and validates an example topology through the installed `chokepoint` command.

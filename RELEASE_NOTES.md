# ChokePoint 1.0.0 Project Notes

Release date: 2026-07-19

ChokePoint 1.0.0 is a portfolio milestone for the infrastructure dependency
graph analyzer. It provides a typed Python API and CLI for ingesting
infrastructure descriptions, constructing dependency graphs, identifying choke
points, and exporting reports for engineering review.

## Highlights

- Python 3.12+ package using `uv`, `pyproject.toml`, and a `src/` layout.
- Unified topology model centered on YAML-defined infrastructure dependencies.
- Basic adapters for Terraform-style and Docker Compose inputs, plus optional
  adapters for Kubernetes, CloudFormation, Pulumi, OpenTofu, Terraform plan, and
  Terraform state data.
- NetworkX-backed graph analysis for articulation points, bridges, components,
  centrality, cycles, and validation.
- Risk engine for shared DNS, identity, CDN, secrets, monitoring, networking,
  CI/CD, email, and single-service articulation risks.
- CLI commands for `analyze`, `graph`, `report`, `validate`, `export`, and
  `diff`.
- Core exports for Markdown, JSON, terminal, CSV, and Mermaid, with optional
  HTML, SARIF, OpenAPI, Graphviz, and interactive HTML outputs.

## Upgrade Notes

This milestone is meant to be understandable and demoable. Public APIs may
evolve as the project is simplified or refined.

## Verification

The project checks passed:

```text
uv run black src tests
uv run ruff check src tests
uv run mypy
uv run pytest
uv build
```

Coverage is enforced at 95% or higher.

# ChokePoint

ChokePoint is a Python CLI tool that builds infrastructure dependency graphs
and detects single points of failure using graph algorithms.

It models services, databases, DNS providers, identity systems, cloud services,
and external dependencies as a graph. ChokePoint then uses NetworkX analysis to
find articulation points, bridge edges, blast radius, and dependency paths.

## Quick Demo

Run the analyzer against one of the included topology examples:

```bash
uv run chokepoint analyze examples/topology-microservices.yaml --markdown
```

The report shows:

- a Mermaid dependency graph
- hidden single points of failure
- articulation points and bridge edges
- blast radius and dependency chains
- confidence, assessment, and evidence for findings

## Core Features

- Parses YAML infrastructure dependency files.
- Builds a typed topology model with Pydantic.
- Converts infrastructure dependencies into a NetworkX graph.
- Detects articulation points, bridge edges, connected components, cycles, and
  centrality.
- Generates terminal, Markdown, JSON, CSV, and Mermaid reports.
- Includes confidence-aware risk findings so graph artifacts are not overstated
  as confirmed real-world issues.
- Provides a Click/Rich CLI for local analysis.

## Optional Experiments

The project also includes optional parser and export adapters for broader
experiments:

- Docker Compose
- Terraform and OpenTofu HCL
- Terraform plan and state JSON
- Kubernetes manifests
- CloudFormation templates
- Pulumi stack exports
- SARIF, OpenAPI, HTML, Graphviz, and interactive HTML exports

These adapters are useful for exploring real repositories, but they are not the
main pitch. The main project story is the graph model and
single-point-of-failure analysis.

## What This Project Demonstrates

ChokePoint is designed as a portfolio-friendly infrastructure graph analyzer. It
demonstrates:

- Python 3.12+ project structure
- typed domain models
- CLI design
- graph algorithms
- parser design
- test coverage and CI
- documentation and project hygiene

## Engineering Baseline

The repository uses modern Python engineering practices:

- `uv` for package and environment management
- `pyproject.toml` as the single project configuration surface
- `src/` package layout
- `pytest` for testing
- `ruff`, `black`, and `mypy` for quality gates
- `pre-commit` hooks
- GitHub Actions CI

## Development

Install the development environment:

```bash
uv sync --extra dev
```

Run the checks used by CI:

```bash
uv sync --extra dev
uv run black --check src tests
uv run ruff check src tests
uv run mypy
uv run pytest
```

Use `uv run pytest`, not a global `pytest` command. The project uses a
`src/` layout and relies on uv to create the Python 3.12+ environment and
install test dependencies before collection.

Install local hooks:

```bash
uv run pre-commit install
```

## CLI

Common commands:

```bash
uv run chokepoint analyze examples/topology-microservices.yaml
uv run chokepoint graph examples/topology-microservices.yaml --json
uv run chokepoint report examples/topology-microservices.yaml --markdown
uv run chokepoint validate examples/topology-microservices.yaml
uv run chokepoint export examples/topology-microservices.yaml --format mermaid
uv run chokepoint diff examples/topology-basic.yaml examples/topology-expanded.yaml --json
```

`analyze` and `report` explain the topology in terms of a visual dependency
graph, hidden single points of failure, blast radius, confidence, evidence, and
why each risky dependency matters.

Use `--verbose` before the command for colored diagnostic logs:

```bash
chokepoint --verbose validate topology.yaml
```

## Architecture

The architecture is documented in [Architecture.md](Architecture.md). The
package is organized around independent layers for parsing, graph construction,
domain models, reporting, visualization, utilities, and the command-line entry
point.

The graph engine algorithms and complexity profile are documented in
[docs/graph-engine.md](docs/graph-engine.md).

The supported YAML topology format is documented in
[docs/yaml-parser.md](docs/yaml-parser.md).

Terraform ingestion is documented in
[docs/terraform-parser.md](docs/terraform-parser.md).

Optional ingestion adapters for Kubernetes, CloudFormation, Docker Compose,
Pulumi, OpenTofu, Terraform plan JSON, and Terraform state JSON are documented
in [docs/advanced-ingestion.md](docs/advanced-ingestion.md).

Terraform enrichment with YAML overlays is documented in
[docs/enrichment.md](docs/enrichment.md).

Risk analysis output is documented in [docs/risk-engine.md](docs/risk-engine.md).

Graphviz visualization is documented in [docs/visualization.md](docs/visualization.md).

Report and topology exports are documented in [docs/exports.md](docs/exports.md).

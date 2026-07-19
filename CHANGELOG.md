# Changelog

All notable changes to ChokePoint are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning.

## [Unreleased]

### Added

- Evidence, confidence, and assessment metadata on risk findings and hidden
  single-point-of-failure report records.
- Export metadata for confidence, assessment, and evidence so automation can
  distinguish confirmed findings from review-needed risks.

### Changed

- Downgrade Docker Compose's implicit `default` network to a modeling artifact
  instead of reporting it as a high-risk shared networking dependency.
- Improve CI/CD classification to avoid labeling CDN names such as `cdnjs` as
  CI/CD dependencies.

## [1.0.0] - 2026-07-19

Portfolio milestone focused on the core infrastructure graph model, CLI, and
single-point-of-failure analysis. Optional parser/export adapters are included
for exploration but are not the main focus.

### Added

- Core `Topology`, `Node`, `Edge`, `NodeType`, and `Relationship` models.
- YAML topology parsing with schema validation and helpful errors.
- Basic Terraform-style and Docker Compose ingestion adapters.
- Optional Kubernetes, CloudFormation, Pulumi, OpenTofu, Terraform plan, and
  Terraform state ingestion adapters.
- YAML overlay enrichment, provider normalization, duplicate detection, and
  topology merging.
- NetworkX graph builder and analyzer for articulation points, bridges,
  connected components, centrality, cycles, and graph validation.
- Risk analysis engine with structured risk reports, blast radius, dependency
  chains, and human-readable explanations.
- Markdown, JSON, terminal, CSV, and Mermaid exports.
- Optional HTML, SARIF, OpenAPI, Graphviz, and interactive graph exports.
- Topology diffing and Click CLI.
- GitHub Actions CI for formatting, linting, type checking, tests, coverage,
  and package builds.
- Project maintenance files, including issue templates, pull request template,
  code of conduct, security policy, and support policy.

### Security

- Interactive HTML graph exports use script-safe JSON encoding and DOM text
  rendering for topology values.
- YAML parsing uses safe loaders or a constrained CloudFormation intrinsic-tag
  loader.
- Graphviz rendering invokes the executable without shell interpolation.

### Quality

- Test suite enforces at least 95% coverage.
- Strict mypy checking, Ruff linting, Black formatting, and pre-commit hooks are
  configured.

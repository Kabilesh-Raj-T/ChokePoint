# Risk Engine

The ChokePoint risk engine consumes a `Topology` or a NetworkX graph produced
from a topology and emits a structured `RiskReport`.

## API

```python
from chokepoint.report import RiskAnalyzer

report = RiskAnalyzer().analyze(topology)
payload = report.export_json()
```

Use `RiskAnalyzer().analyze_graph(graph)` when the caller already has a
ChokePoint NetworkX graph.

## Rule Levels

| Level | Rules |
| --- | --- |
| Critical | Shared DNS, shared identity, shared CDN, shared secrets manager |
| High | Shared monitoring, shared networking |
| Medium | Shared CI/CD, shared email |
| Low | Single-service articulation |

Shared dependency rules trigger when at least two nodes directly or transitively
depend on a categorized node. Single-service articulation uses graph
articulation data and reports low risk when an articulation point sits on one
service dependency path.

## Report Fields

Each finding includes:

- `risk_score`
- `criticality`
- `confidence`
- `assessment`
- `blast_radius`
- `dependency_chain`
- `impacted_nodes`
- `impacted_providers`
- `evidence`
- `explanation`

The report-level `risk_score` is the highest finding score. Scores are bounded
from `0` to `100` and combine severity, blast radius, and provider diversity.

## Trust Model

ChokePoint separates graph facts from interpretation so reports are useful
without overstating confidence. Every finding includes:

- `confidence`: `high`, `medium`, or `low`
- `assessment`: `confirmed`, `likely`, `needs_review`, or `modeling_artifact`
- `evidence`: compact records containing the parser, source file when known,
  source line when available, evidence kind, subject, and explanation

Explicitly typed dependencies, such as a node declared as `dns` or `identity`,
produce higher-confidence findings. Name/provider matches, such as
`cloudflare`, `datadog`, or `github-actions`, are heuristic and are reported as
likely unless stronger source data is available.

Known local-topology artifacts are downgraded. For example, Docker Compose's
implicit `default` network is marked as a `modeling_artifact` instead of a
high-risk shared networking dependency. This keeps ChokePoint's output suitable
for review rather than presenting every structural feature as a real-world
defect.

Generated reports also include:

- `dependency_graph`: normalized edges used to render the topology as a
  Mermaid dependency graph.
- `single_points_of_failure`: one explanatory record per risky shared
  dependency or structural articulation point, including severity, confidence,
  assessment, category, blast radius, impacted nodes, evidence, and
  `why_it_matters` text for human review.

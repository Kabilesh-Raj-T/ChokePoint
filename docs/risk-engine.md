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
- `blast_radius`
- `dependency_chain`
- `impacted_nodes`
- `impacted_providers`
- `explanation`

The report-level `risk_score` is the highest finding score. Scores are bounded
from `0` to `100` and combine severity, blast radius, and provider diversity.

Generated reports also include:

- `dependency_graph`: normalized edges used to render the topology as a
  Mermaid dependency graph.
- `single_points_of_failure`: one explanatory record per risky shared
  dependency or structural articulation point, including severity, category,
  blast radius, impacted nodes, and `why_it_matters` text for human review.

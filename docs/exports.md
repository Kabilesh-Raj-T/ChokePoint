# Exports

ChokePoint exports topology and report data for automation, engineering review,
and documentation workflows.

## CLI

```bash
chokepoint export topology.yaml --format sarif
chokepoint export topology.yaml --format openapi
chokepoint export topology.yaml --format csv
chokepoint export topology.yaml --format mermaid
chokepoint export topology.yaml --format html
```

## API

```python
from chokepoint.report import (
    export_csv,
    export_mermaid,
    export_openapi,
    export_sarif,
    generate_security_report,
)

report = generate_security_report(topology)
sarif = export_sarif(report)
csv_payload = export_csv(topology)
```

Markdown and HTML reports include a dependency graph section plus a hidden
single-points-of-failure section. The Markdown graph is emitted as Mermaid so
GitHub can render it visually in issues, pull requests, and project notes.

SARIF results include ChokePoint-specific properties for `riskScore`,
`confidence`, `assessment`, `blastRadius`, `impactedNodes`, and `evidence`.
This lets automation distinguish confirmed findings from likely risks,
review-required structural findings, and known modeling artifacts.

## Diff

Topology diffs are available through the graph API and CLI:

```bash
chokepoint diff before.yaml after.yaml --json
```

```python
from chokepoint.graph import diff_topologies

diff = diff_topologies(before, after)
```

The diff reports added, removed, and changed nodes plus added and removed
edges.

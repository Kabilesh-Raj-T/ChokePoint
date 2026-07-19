# Exports

ChokePoint exports topology and report data for local review and documentation.

## CLI

```bash
chokepoint export topology.yaml --format csv
chokepoint export topology.yaml --format mermaid
```

## API

```python
from chokepoint.report import export_csv, export_mermaid

csv_payload = export_csv(topology)
mermaid_payload = export_mermaid(topology)
```

Markdown reports include a dependency graph section rendered as Mermaid, which
GitHub can display in issues, pull requests, and project notes.

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

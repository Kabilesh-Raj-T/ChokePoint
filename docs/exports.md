# Exports

BlastRadius exports topology and report data for local review and documentation.

## CLI

```bash
blastradius export topology.yaml --format csv
blastradius export topology.yaml --format mermaid
blastradius export topology.yaml --format svg
```

## API

```python
from blastradius.report import export_csv, export_mermaid, export_svg

csv_payload = export_csv(topology)
mermaid_payload = export_mermaid(topology)
svg_payload = export_svg(topology)
```

Markdown reports include a dependency graph section rendered as Mermaid, which
GitHub can display in issues, pull requests, and project notes.

## Diff

Topology diffs are available through the graph API and CLI:

```bash
blastradius diff before.yaml after.yaml --json
```

```python
from blastradius.graph import diff_topologies

diff = diff_topologies(before, after)
```

The diff reports added, removed, and changed nodes plus added and removed
edges.

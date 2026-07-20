# Repository Scanner

`chokepoint scan` is the best command for trying ChokePoint on an arbitrary
repository.

```bash
uv run chokepoint scan /path/to/repo --markdown
uv run chokepoint scan /path/to/repo --json
```

The scanner discovers supported files, parses what it can, and records
non-fatal issues for files it cannot parse.

## Supported Discovery

- ChokePoint topology files such as `topology.yaml`, `topology.yml`, and
  `topology-*.yaml`.
- Terraform directories containing `.tf` files.
- Docker Compose files such as `compose.yaml`, `docker-compose.yml`, and
  `*compose*.yaml`.

Common generated or dependency directories such as `.git`, `.terraform`,
`.venv`, `node_modules`, `build`, and `dist` are skipped.

## Merged Topology

Each parsed artifact is namespaced before being merged into one topology. This
prevents collisions when multiple Terraform modules use the same resource
address, such as `aws_vpc.this`.

Node and edge metadata include:

- `artifact_kind`
- `artifact_path`
- `original_id`

## Limits

The scanner is best-effort. It improves compatibility with normal repositories,
but it does not claim to understand every infrastructure tool or every runtime
dependency. Unsupported files are skipped, and low-confidence findings should be
reviewed with service owners.

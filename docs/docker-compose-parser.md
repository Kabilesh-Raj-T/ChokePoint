# Docker Compose Parser

ChokePoint can parse basic Docker Compose YAML into a topology.

## API

```python
from chokepoint.parser import DockerComposeParser

topology = DockerComposeParser().parse_file("docker-compose.yml")
```

Available entry points:

- `parse_docker_compose_text(payload, source="<string>")`
- `parse_docker_compose_file(path)`
- `DockerComposeParser().parse_file(path)`

## What It Extracts

- Compose services as service nodes.
- `depends_on` relationships between services.
- Referenced networks as network nodes.
- Referenced volumes as storage nodes.
- Referenced secrets as secret nodes.

This parser is intentionally small. It is useful for demos and simple local
Compose files, but it does not try to fully emulate Docker Compose resolution.

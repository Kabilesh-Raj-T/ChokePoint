"""Repository auto-discovery for supported BlastRadius inputs."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from blastradius.models import Edge, Node, Topology
from blastradius.models.topology import Metadata
from blastradius.parser.docker_compose_parser import parse_docker_compose_file
from blastradius.parser.terraform_parser import parse_terraform_directory
from blastradius.parser.yaml_parser import parse_topology_yaml_file

type RepositoryArtifactKind = Literal[
    "topology_yaml",
    "terraform",
    "docker_compose",
]

COMPOSE_FILE_NAMES = {
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
}
TOPOLOGY_FILE_NAMES = {
    "blastradius.yaml",
    "blastradius.yml",
    "topology.yaml",
    "topology.yml",
}
SKIPPED_DIRECTORIES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".terraform",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


class RepositoryArtifact(BaseModel):
    """Supported file or directory discovered during repository scanning."""

    model_config = ConfigDict(frozen=True)

    kind: RepositoryArtifactKind
    path: str
    nodes: int = Field(ge=0)
    edges: int = Field(ge=0)


class RepositoryScanIssue(BaseModel):
    """Non-fatal parse issue found during repository scanning."""

    model_config = ConfigDict(frozen=True)

    kind: RepositoryArtifactKind
    path: str
    error: str


class RepositoryScanResult(BaseModel):
    """Repository scan result with a merged topology and parse diagnostics."""

    model_config = ConfigDict(frozen=True)

    root: str
    topology: Topology
    artifacts: tuple[RepositoryArtifact, ...]
    issues: tuple[RepositoryScanIssue, ...]


class RepositoryScanner:
    """Discover supported infrastructure files in an arbitrary repository."""

    def scan(self, path: str | Path) -> RepositoryScanResult:
        """Scan a repository path and merge every supported topology.

        Args:
            path: Repository root or project directory.

        Returns:
            Repository scan result with a best-effort merged topology.

        Raises:
            ValueError: If the supplied path is not a directory.
        """
        root = Path(path)
        if not root.exists():
            message = f"repository path does not exist: {root}"
            raise ValueError(message)
        if not root.is_dir():
            message = f"repository path must be a directory: {root}"
            raise ValueError(message)

        resolved_root = root.resolve()
        state = _ScanState(root=resolved_root, topology=Topology())

        for topology_path in _discover_topology_files(resolved_root):
            _parse_artifact(
                state=state,
                artifact_path=topology_path,
                kind="topology_yaml",
                parser=parse_topology_yaml_file,
            )

        for terraform_dir in _discover_terraform_directories(resolved_root):
            _parse_artifact(
                state=state,
                artifact_path=terraform_dir,
                kind="terraform",
                parser=parse_terraform_directory,
            )

        for compose_path in _discover_compose_files(resolved_root):
            _parse_artifact(
                state=state,
                artifact_path=compose_path,
                kind="docker_compose",
                parser=parse_docker_compose_file,
            )

        return RepositoryScanResult(
            root=str(resolved_root),
            topology=state.topology,
            artifacts=tuple(state.artifacts),
            issues=tuple(state.issues),
        )


def scan_repository(path: str | Path) -> RepositoryScanResult:
    """Scan a repository using the default repository scanner."""
    return RepositoryScanner().scan(path)


@dataclass
class _ScanState:
    root: Path
    topology: Topology
    artifacts: list[RepositoryArtifact]
    issues: list[RepositoryScanIssue]

    def __init__(self, *, root: Path, topology: Topology) -> None:
        self.root = root
        self.topology = topology
        self.artifacts = []
        self.issues = []


def _parse_artifact(
    *,
    state: _ScanState,
    artifact_path: Path,
    kind: RepositoryArtifactKind,
    parser: Callable[[Path], Topology],
) -> None:
    relative_path = _relative_path(artifact_path, state.root)
    try:
        artifact_topology = parser(artifact_path)
    except Exception as error:
        state.issues.append(
            RepositoryScanIssue(
                kind=kind,
                path=relative_path,
                error=str(error),
            )
        )
        return

    _merge_topology(
        target=state.topology,
        source=artifact_topology,
        kind=kind,
        artifact_path=relative_path,
    )
    state.artifacts.append(
        RepositoryArtifact(
            kind=kind,
            path=relative_path,
            nodes=len(artifact_topology.nodes),
            edges=len(artifact_topology.edges),
        )
    )


def _merge_topology(
    *,
    target: Topology,
    source: Topology,
    kind: RepositoryArtifactKind,
    artifact_path: str,
) -> None:
    prefix = _artifact_prefix(kind, artifact_path)
    node_id_map: dict[str, str] = {}

    for node in source.nodes.values():
        namespaced_id = f"{prefix}:{node.id}"
        node_id_map[node.id] = namespaced_id
        metadata = _artifact_metadata(
            node.metadata,
            kind=kind,
            artifact_path=artifact_path,
            original_id=node.id,
        )
        target.add_node(
            Node(
                id=namespaced_id,
                name=node.name,
                provider=node.provider,
                node_type=node.node_type,
                metadata=metadata,
            )
        )

    for edge in source.edges:
        metadata = _artifact_metadata(
            edge.metadata,
            kind=kind,
            artifact_path=artifact_path,
            original_id=f"{edge.source}->{edge.target}",
        )
        target.add_edge(
            Edge(
                source=node_id_map[edge.source],
                target=node_id_map[edge.target],
                relationship=edge.relationship,
                metadata=metadata,
            )
        )


def _artifact_metadata(
    metadata: Metadata,
    *,
    kind: RepositoryArtifactKind,
    artifact_path: str,
    original_id: str,
) -> Metadata:
    return {
        **metadata,
        "artifact_kind": kind,
        "artifact_path": artifact_path,
        "original_id": original_id,
    }


def _discover_topology_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(file for file in _walk_files(root) if _is_topology_file(file)))


def _discover_terraform_directories(root: Path) -> tuple[Path, ...]:
    directories = {file.parent for file in _walk_files(root) if file.suffix == ".tf"}
    return tuple(sorted(directories))


def _discover_compose_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(file for file in _walk_files(root) if _is_compose_file(file)))


def _walk_files(root: Path) -> Iterable[Path]:
    for current_root, directory_names, file_names in os.walk(root):
        directory_names[:] = [
            directory
            for directory in directory_names
            if directory not in SKIPPED_DIRECTORIES
        ]
        current_path = Path(current_root)
        for file_name in file_names:
            yield current_path / file_name


def _is_topology_file(path: Path) -> bool:
    name = path.name.lower()
    return name in TOPOLOGY_FILE_NAMES or (
        name.startswith("topology-") and path.suffix.lower() in {".yaml", ".yml"}
    )


def _is_compose_file(path: Path) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()
    return suffix in {".yaml", ".yml"} and (
        name in COMPOSE_FILE_NAMES or "compose" in name
    )


def _relative_path(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return str(path)
    return "." if not relative.parts else relative.as_posix()


def _artifact_prefix(kind: RepositoryArtifactKind, artifact_path: str) -> str:
    raw_value = f"{kind}:{artifact_path}"
    safe_value = "".join(
        character if character.isalnum() else "_" for character in raw_value
    )
    return safe_value.strip("_") or kind

"""Repository scanner tests."""

from pathlib import Path

from chokepoint.parser import RepositoryScanner, scan_repository

MINIMUM_MERGED_NODES = 6


def test_scan_repository_merges_supported_artifacts(tmp_path: Path) -> None:
    write_repository_fixture(tmp_path)

    result = scan_repository(tmp_path)

    assert result.root == str(tmp_path.resolve())
    assert result.issues == ()
    assert {artifact.kind for artifact in result.artifacts} == {
        "docker_compose",
        "terraform",
        "topology_yaml",
    }
    assert len(result.topology.nodes) >= MINIMUM_MERGED_NODES
    assert all("node_modules" not in node_id for node_id in result.topology.nodes)
    assert all(
        node.id.startswith(str(node.metadata["artifact_kind"]))
        for node in result.topology.nodes.values()
    )
    assert {
        node.metadata["artifact_path"] for node in result.topology.nodes.values()
    } >= {"docker-compose.yml", "infra", "topology.yaml"}


def test_scan_repository_records_non_fatal_parse_issues(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text(
        """
services:
  api:
    image: example/api
""",
        encoding="utf-8",
    )
    (tmp_path / "broken-compose.yml").write_text("services: [", encoding="utf-8")

    result = RepositoryScanner().scan(tmp_path)

    assert len(result.artifacts) == 1
    assert result.artifacts[0].kind == "docker_compose"
    assert len(result.issues) == 1
    assert result.issues[0].path == "broken-compose.yml"
    assert "malformed YAML" in result.issues[0].error


def test_scan_repository_with_no_supported_files_returns_empty_topology(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert result.artifacts == ()
    assert result.issues == ()
    assert result.topology.nodes == {}
    assert result.topology.edges == []


def test_scan_repository_rejects_non_directory(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("# Project\n", encoding="utf-8")

    try:
        scan_repository(path)
    except ValueError as error:
        assert "must be a directory" in str(error)
    else:
        raise AssertionError("expected repository scanner to reject a file path")


def write_repository_fixture(root: Path) -> None:
    (root / "topology.yaml").write_text(
        """
external:
  - cloudflare
services:
  web:
    depends_on:
      - cloudflare
""",
        encoding="utf-8",
    )
    (root / "docker-compose.yml").write_text(
        """
services:
  api:
    depends_on:
      - db
  db:
    volumes:
      - db-data:/var/lib/postgresql/data
volumes:
  db-data:
""",
        encoding="utf-8",
    )
    infra = root / "infra"
    infra.mkdir()
    (infra / "main.tf").write_text(
        """
resource "aws_vpc" "main" {}
resource "aws_subnet" "public" {
  vpc_id = aws_vpc.main.id
}
""",
        encoding="utf-8",
    )
    ignored = root / "node_modules"
    ignored.mkdir()
    (ignored / "docker-compose.yml").write_text("services: [", encoding="utf-8")

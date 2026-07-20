"""CLI integration tests for ChokePoint."""

import json
from pathlib import Path

from click.testing import CliRunner

import chokepoint.cli.app as cli_app
from chokepoint.cli import cli

EXPECTED_GRAPH_NODES = 5
EXPECTED_GRAPH_EDGES = 2


TOPOLOGY_YAML = """
clouds:
  - aws
  - azure

dns:
  - cloudflare

services:
  aws-api:
    depends_on:
      - cloudflare
  azure-api:
    depends_on:
      - cloudflare
"""


def write_topology(tmp_path: Path, payload: str = TOPOLOGY_YAML) -> Path:
    path = tmp_path / "topology.yaml"
    path.write_text(payload, encoding="utf-8")
    return path


def test_validate_json_reports_valid_topology(tmp_path: Path) -> None:
    path = write_topology(tmp_path)

    result = CliRunner().invoke(cli, ["validate", str(path), "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"valid": True, "nodes": 5, "edges": 2}


def test_validate_reports_parse_error(tmp_path: Path) -> None:
    path = write_topology(
        tmp_path,
        """
services:
  frontend:
    depends_on:
      - missing
""",
    )

    result = CliRunner().invoke(cli, ["validate", str(path)])

    assert result.exit_code == 1
    assert "dependency target 'missing' is not defined" in result.output


def test_analyze_json_outputs_risk_report(tmp_path: Path) -> None:
    path = write_topology(tmp_path)

    result = CliRunner().invoke(cli, ["analyze", str(path), "--json"])

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["title"] == "ChokePoint Security Report"
    assert payload["risk_report"]["finding_count"] >= 1
    assert {finding["category"] for finding in payload["risk_report"]["findings"]} >= {
        "dns"
    }
    assert payload["critical_dependencies"][0]["node_id"] == "cloudflare"
    assert payload["critical_dependencies"][0]["confidence"] == "high"
    assert payload["dependency_graph"][0]["target"] == "cloudflare"
    assert payload["single_points_of_failure"][0]["node_id"] == "cloudflare"
    assert payload["single_points_of_failure"][0]["confidence"] == "high"
    assert "why_it_matters" in payload["single_points_of_failure"][0]


def test_report_markdown_outputs_heading(tmp_path: Path) -> None:
    path = write_topology(tmp_path)

    result = CliRunner().invoke(cli, ["report", str(path), "--markdown"])

    assert result.exit_code == 0
    assert "ChokePoint Security Report" in result.output
    assert "## Executive Summary" in result.output
    assert "## Dependency Graph" in result.output
    assert "```mermaid" in result.output
    assert "## Hidden Single Points of Failure" in result.output
    assert "## Critical Dependencies" in result.output
    assert "Cloudflare" in result.output or "cloudflare" in result.output


def test_graph_json_outputs_graph_metrics(tmp_path: Path) -> None:
    path = write_topology(tmp_path)

    result = CliRunner().invoke(cli, ["graph", str(path), "--json"])

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["node_count"] == EXPECTED_GRAPH_NODES
    assert payload["edge_count"] == EXPECTED_GRAPH_EDGES
    assert payload["articulation_points"] == ["cloudflare"]


def test_graph_markdown_outputs_summary(tmp_path: Path) -> None:
    path = write_topology(tmp_path)

    result = CliRunner().invoke(cli, ["graph", str(path), "--markdown"])

    assert result.exit_code == 0
    assert "ChokePoint Graph Summary" in result.output


def test_graph_default_outputs_table(tmp_path: Path) -> None:
    path = write_topology(tmp_path)

    result = CliRunner().invoke(cli, ["graph", str(path)])

    assert result.exit_code == 0
    assert "Graph Summary" in result.output
    assert "Articulation points" in result.output


def test_export_csv_outputs_dependency_rows(tmp_path: Path) -> None:
    path = write_topology(tmp_path)

    result = CliRunner().invoke(cli, ["export", str(path), "--format", "csv"])

    assert result.exit_code == 0
    assert "source,target,relationship" in result.output
    assert "aws-api,cloudflare,depends_on" in result.output


def test_export_mermaid_outputs_graph(tmp_path: Path) -> None:
    path = write_topology(tmp_path)

    result = CliRunner().invoke(cli, ["export", str(path), "--format", "mermaid"])

    assert result.exit_code == 0
    assert result.output.startswith("flowchart LR")


def test_analyze_reports_parse_error(tmp_path: Path) -> None:
    path = write_topology(tmp_path, "services: frontend")

    result = CliRunner().invoke(cli, ["analyze", str(path)])

    assert result.exit_code == 1
    assert "$.services must be a mapping" in result.output


def test_graph_reports_parse_error(tmp_path: Path) -> None:
    path = write_topology(tmp_path, "services: frontend")

    result = CliRunner().invoke(cli, ["graph", str(path)])

    assert result.exit_code == 1
    assert "$.services must be a mapping" in result.output


def test_report_reports_parse_error(tmp_path: Path) -> None:
    path = write_topology(tmp_path, "services: frontend")

    result = CliRunner().invoke(cli, ["report", str(path)])

    assert result.exit_code == 1
    assert "$.services must be a mapping" in result.output


def test_export_reports_parse_error(tmp_path: Path) -> None:
    path = write_topology(tmp_path, "services: frontend")

    result = CliRunner().invoke(cli, ["export", str(path), "--format", "csv"])

    assert result.exit_code == 1
    assert "$.services must be a mapping" in result.output


def test_diff_reports_parse_error(tmp_path: Path) -> None:
    before = write_topology(tmp_path, "services: frontend")
    after = tmp_path / "after.yaml"
    after.write_text(TOPOLOGY_YAML, encoding="utf-8")

    result = CliRunner().invoke(cli, ["diff", str(before), str(after)])

    assert result.exit_code == 1
    assert "$.services must be a mapping" in result.output


def test_unexpected_cli_error_is_wrapped(tmp_path: Path, monkeypatch) -> None:
    path = write_topology(tmp_path)

    def raise_runtime_error(_: Path):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_app, "parse_topology_yaml_file", raise_runtime_error)

    result = CliRunner().invoke(cli, ["validate", str(path)])

    assert result.exit_code == 1
    assert "unexpected error: boom" in result.output


def test_diff_json_outputs_topology_changes(tmp_path: Path) -> None:
    before = write_topology(tmp_path)
    after = tmp_path / "after.yaml"
    after.write_text(
        TOPOLOGY_YAML
        + """
identity:
  - okta
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["diff", str(before), str(after), "--json"])

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["added_nodes"][0]["id"] == "okta"


def test_diff_markdown_outputs_summary(tmp_path: Path) -> None:
    before = write_topology(tmp_path)
    after = tmp_path / "after.yaml"
    after.write_text(
        TOPOLOGY_YAML
        + """
identity:
  - okta
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["diff", str(before), str(after)])

    assert result.exit_code == 0
    assert "ChokePoint Topology Diff" in result.output
    assert "Added nodes" in result.output


def test_validate_non_json_success_output(tmp_path: Path) -> None:
    path = write_topology(tmp_path)

    result = CliRunner().invoke(cli, ["validate", str(path)])

    assert result.exit_code == 0
    assert "Valid topology" in result.output


def test_validate_json_reports_parse_error(tmp_path: Path) -> None:
    path = write_topology(tmp_path, "services: frontend")

    result = CliRunner().invoke(cli, ["validate", str(path), "--json"])

    assert result.exit_code == 1
    assert '"valid": false' in result.output.lower()


def test_analyze_rich_output_contains_table_data(tmp_path: Path) -> None:
    path = write_topology(tmp_path)

    result = CliRunner().invoke(cli, ["analyze", str(path)])

    assert result.exit_code == 0
    assert "Risk Score" in result.output
    assert "Critical Dependencies" in result.output
    assert "Dependency Graph" in result.output
    assert "Hidden Single Points of Failure" in result.output
    assert "Dependency Table" in result.output


def test_verbose_error_includes_command_failed_log(tmp_path: Path) -> None:
    path = write_topology(tmp_path, "services: frontend")

    result = CliRunner().invoke(cli, ["--verbose", "validate", str(path)])

    assert result.exit_code == 1
    assert "Command failed" in result.output
    assert "$.services must be a mapping" in result.output


def test_help_lists_commands() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "analyze" in result.output
    assert "diff" in result.output
    assert "export" in result.output
    assert "graph" in result.output
    assert "report" in result.output
    assert "validate" in result.output


def test_main_delegates_to_click(monkeypatch) -> None:
    called = False

    def fake_cli() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(cli_app, "cli", fake_cli)

    cli_app.main()

    assert called

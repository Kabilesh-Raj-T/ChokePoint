"""Report generator tests for ChokePoint."""

from __future__ import annotations

import io
import json

from rich.console import Console

from chokepoint.models import Edge, Node, NodeType, Relationship, Topology
from chokepoint.report import GeneratedReport, generate_security_report

EXPECTED_DEPENDENCY_ROWS = 2
EXPECTED_NODE_COUNT = 3
EXPECTED_RISK_SCORE = 98
COMPOSE_SERVICE_BLAST_RADIUS = 2
SECURITY_REPORT_RECOMMENDATION = (
    "No immediate choke-point risks were detected; continue monitoring topology drift."
)


def test_generate_security_report_returns_structured_report() -> None:
    topology = shared_dns_topology()

    report = generate_security_report(topology)

    assert isinstance(report, GeneratedReport)
    assert report.title == "ChokePoint Security Report"
    assert report.risk_score == EXPECTED_RISK_SCORE
    assert report.critical_dependencies
    assert report.dependency_graph[0].source == "aws-api"
    assert len(report.single_points_of_failure) == 1
    assert report.single_points_of_failure[0].node_id == "cloudflare"
    assert report.single_points_of_failure[0].category == "dns, cdn"
    assert report.single_points_of_failure[0].confidence.value == "medium"
    assert report.single_points_of_failure[0].assessment.value == "likely"
    assert report.single_points_of_failure[0].evidence
    assert "shared DNS and CDN dependency" in (
        report.single_points_of_failure[0].why_it_matters
    )
    assert report.articulation_points == ("cloudflare",)
    assert report.bridge_edges
    assert len(report.dependency_table) == EXPECTED_DEPENDENCY_ROWS
    assert report.blast_radius["cloudflare"] == EXPECTED_DEPENDENCY_ROWS


def test_report_json_contains_nested_security_context() -> None:
    report = generate_security_report(shared_dns_topology())

    payload = json.loads(report.to_json())

    assert payload["executive_summary"].startswith("ChokePoint analyzed")
    assert payload["risk_report"]["finding_count"] >= 1
    assert payload["graph_report"]["node_count"] == EXPECTED_NODE_COUNT
    assert payload["dependency_graph"][0]["target"] == "cloudflare"
    assert payload["risk_report"]["findings"][0]["confidence"]
    assert payload["risk_report"]["findings"][0]["assessment"]
    assert payload["risk_report"]["findings"][0]["evidence"]
    assert payload["single_points_of_failure"][0]["why_it_matters"]
    assert payload["single_points_of_failure"][0]["confidence"]
    assert payload["single_points_of_failure"][0]["assessment"]
    assert payload["single_points_of_failure"][0]["evidence"]
    assert payload["dependency_table"][0]["relationship"] == "depends_on"
    assert payload["critical_dependencies"][0]["dependency_chain"]


def test_report_markdown_is_github_security_report_friendly() -> None:
    report = generate_security_report(shared_dns_topology())

    markdown = report.to_markdown()

    assert markdown.startswith("# ChokePoint Security Report")
    assert "## Executive Summary" in markdown
    assert "## Risk Score" in markdown
    assert "## Dependency Graph" in markdown
    assert "```mermaid" in markdown
    assert "SPOF: critical DNS" in markdown
    assert "## Hidden Single Points of Failure" in markdown
    assert "Confidence: `medium`" in markdown
    assert "Assessment: `likely`" in markdown
    assert "Evidence:" in markdown
    assert "Why it matters:" in markdown
    assert "## Critical Dependencies" in markdown
    assert "## Articulation Points" in markdown
    assert "## Bridge Edges" in markdown
    assert "## Recommendations" in markdown
    assert "## Dependency Table" in markdown
    assert "## Blast Radius" in markdown
    assert "| Level | Confidence | Assessment | Category | Node | Score |" in markdown


def test_report_html_is_standalone_and_escaped() -> None:
    topology = Topology()
    topology.add_node(
        Node(
            id="cloudflare",
            name="Cloudflare <DNS>",
            provider="cloudflare",
            node_type=NodeType.DNS,
        )
    )
    topology.add_node(
        Node(
            id="frontend",
            name="Frontend",
            provider="aws",
            node_type=NodeType.SERVICE,
        )
    )
    topology.add_node(
        Node(
            id="api",
            name="API",
            provider="azure",
            node_type=NodeType.SERVICE,
        )
    )
    topology.add_edge(
        Edge(
            source="frontend",
            target="cloudflare",
            relationship=Relationship.DEPENDS_ON,
        )
    )
    topology.add_edge(
        Edge(
            source="api",
            target="cloudflare",
            relationship=Relationship.DEPENDS_ON,
        )
    )

    html = generate_security_report(topology).to_html()

    assert html.startswith("<!doctype html>")
    assert "<h2>Executive Summary</h2>" in html
    assert "<h2>Dependency Graph</h2>" in html
    assert "<h2>Hidden Single Points of Failure</h2>" in html
    assert "<th>Confidence</th>" in html
    assert "<th>Assessment</th>" in html
    assert "Cloudflare &lt;DNS&gt;" in html
    assert "<table>" in html
    assert "<h2>Blast Radius</h2>" in html


def test_terminal_report_renders_expected_sections() -> None:
    report = generate_security_report(shared_dns_topology())
    stream = io.StringIO()
    console = Console(file=stream, width=120, force_terminal=False)

    console.print(report.to_terminal())

    output = stream.getvalue()
    assert "ChokePoint Security Report" in output
    assert "Critical Dependencies" in output
    assert "Dependency Graph" in output
    assert "Hidden Single Points of Failure" in output
    assert "Graph Choke Points" in output
    assert "Recommendations" in output
    assert "Dependency Table" in output


def test_report_empty_states_are_explicit() -> None:
    topology = Topology()
    topology.add_node(
        Node(
            id="frontend",
            name="Frontend",
            provider="aws",
            node_type=NodeType.SERVICE,
        )
    )

    report = generate_security_report(topology)
    markdown = report.to_markdown()
    html = report.to_html()
    stream = io.StringIO()
    console = Console(file=stream, width=120, force_terminal=False)
    console.print(report.to_terminal())

    assert report.risk_score == 0
    assert report.recommendations == (SECURITY_REPORT_RECOMMENDATION,)
    assert report.single_points_of_failure == ()
    assert "No critical dependencies detected." in markdown
    assert "No hidden single points of failure detected." in markdown
    assert "No dependencies declared." in markdown
    assert "None detected." in html
    assert "No single points detected." in stream.getvalue()


def test_structural_single_point_explains_articulation_without_risk_rule() -> None:
    topology = Topology()
    topology.add_node(
        Node(
            id="public-service",
            name="Public Service",
            provider="kubernetes",
            node_type=NodeType.LOAD_BALANCER,
        )
    )
    topology.add_node(
        Node(
            id="internal-service",
            name="Internal Service",
            provider="kubernetes",
            node_type=NodeType.LOAD_BALANCER,
        )
    )
    topology.add_node(
        Node(
            id="statefulset",
            name="CockroachDB StatefulSet",
            provider="kubernetes",
            node_type=NodeType.SERVICE,
        )
    )
    topology.add_edge(
        Edge(
            source="public-service",
            target="statefulset",
            relationship=Relationship.ROUTES_TO,
        )
    )
    topology.add_edge(
        Edge(
            source="internal-service",
            target="statefulset",
            relationship=Relationship.ROUTES_TO,
        )
    )

    report = generate_security_report(topology)
    markdown = report.to_markdown()

    assert report.risk_score == 0
    assert report.single_points_of_failure[0].node_id == "statefulset"
    assert report.single_points_of_failure[0].severity is None
    assert report.single_points_of_failure[0].confidence.value == "medium"
    assert report.single_points_of_failure[0].assessment.value == "needs_review"
    assert report.single_points_of_failure[0].evidence
    assert "structural cut point" in report.single_points_of_failure[0].why_it_matters
    assert "structural articulation" in markdown


def test_structural_single_point_omits_compose_support_artifacts() -> None:
    topology = Topology()
    for service_id in ("auth", "rest"):
        topology.add_node(
            Node(
                id=f"compose:service:{service_id}",
                name=service_id,
                provider="docker",
                node_type=NodeType.SERVICE,
                metadata={"platform": "docker-compose"},
            )
        )
    topology.add_node(
        Node(
            id="compose:service:db",
            name="db",
            provider="docker",
            node_type=NodeType.SERVICE,
            metadata={"platform": "docker-compose"},
        )
    )
    for volume_id in ("compose:volume:data", "compose:volume:config"):
        topology.add_node(
            Node(
                id=volume_id,
                name=volume_id.rsplit(":", maxsplit=1)[-1],
                provider="docker",
                node_type=NodeType.STORAGE,
                metadata={"platform": "docker-compose"},
            )
        )
    for service_id in ("auth", "rest"):
        topology.add_edge(
            Edge(
                source=f"compose:service:{service_id}",
                target="compose:service:db",
                relationship=Relationship.DEPENDS_ON,
            )
        )
    for volume_id in ("compose:volume:data", "compose:volume:config"):
        topology.add_edge(
            Edge(
                source="compose:service:db",
                target=volume_id,
                relationship=Relationship.DEPENDS_ON,
            )
        )

    report = generate_security_report(topology)
    db_point = next(
        point
        for point in report.single_points_of_failure
        if point.node_id == "compose:service:db"
    )

    assert db_point.blast_radius == COMPOSE_SERVICE_BLAST_RADIUS
    assert db_point.impacted_nodes == ("compose:service:auth", "compose:service:rest")
    assert "2 local Compose support artifact" in db_point.why_it_matters


def shared_dns_topology() -> Topology:
    topology = Topology()
    topology.add_node(
        Node(
            id="cloudflare",
            name="Cloudflare",
            provider="cloudflare",
            node_type=NodeType.DNS,
        )
    )
    topology.add_node(
        Node(
            id="aws-api",
            name="AWS API",
            provider="aws",
            node_type=NodeType.SERVICE,
        )
    )
    topology.add_node(
        Node(
            id="azure-api",
            name="Azure API",
            provider="azure",
            node_type=NodeType.SERVICE,
        )
    )
    topology.add_edge(
        Edge(
            source="aws-api",
            target="cloudflare",
            relationship=Relationship.DEPENDS_ON,
        )
    )
    topology.add_edge(
        Edge(
            source="azure-api",
            target="cloudflare",
            relationship=Relationship.DEPENDS_ON,
        )
    )
    return topology

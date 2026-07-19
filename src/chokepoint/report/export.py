"""Security report and topology export formats."""

from __future__ import annotations

import csv
import io

from chokepoint.models import Topology


class ReportExporter:
    """Export ChokePoint data to integration-friendly formats."""

    def csv(self, topology: Topology) -> str:
        """Export topology dependency edges as CSV."""
        stream = io.StringIO()
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "source",
                "target",
                "relationship",
                "source_provider",
                "target_provider",
                "source_type",
                "target_type",
            ]
        )
        for edge in sorted(
            topology.edges,
            key=lambda item: (item.source, item.target, item.relationship.value),
        ):
            source = topology.nodes[edge.source]
            target = topology.nodes[edge.target]
            writer.writerow(
                [
                    edge.source,
                    edge.target,
                    edge.relationship.value,
                    source.provider,
                    target.provider,
                    source.node_type.value,
                    target.node_type.value,
                ]
            )
        return stream.getvalue()

    def mermaid(self, topology: Topology) -> str:
        """Export topology as a Mermaid flowchart."""
        lines = ["flowchart LR"]
        for node in sorted(topology.nodes.values(), key=lambda item: item.id):
            lines.append(f'  {_mermaid_id(node.id)}["{_escape_mermaid(node.name)}"]')
        for edge in sorted(
            topology.edges,
            key=lambda item: (item.source, item.target, item.relationship.value),
        ):
            lines.append(
                "  "
                f"{_mermaid_id(edge.source)} -->|{edge.relationship.value}| "
                f"{_mermaid_id(edge.target)}"
            )
        return "\n".join(lines) + "\n"


def export_csv(topology: Topology) -> str:
    """Export topology dependencies as CSV."""
    return ReportExporter().csv(topology)


def export_mermaid(topology: Topology) -> str:
    """Export topology dependencies as Mermaid."""
    return ReportExporter().mermaid(topology)


def _mermaid_id(value: str) -> str:
    return "n_" + "".join(
        character if character.isalnum() else "_" for character in value
    )


def _escape_mermaid(value: str) -> str:
    return value.replace('"', '\\"')

"""Security report and topology export formats."""

from __future__ import annotations

import csv
import html
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

    def svg(self, topology: Topology) -> str:
        """Export topology as a dependency graph SVG."""
        node_width = 180
        node_height = 48
        horizontal_gap = 80
        vertical_gap = 28
        margin = 24
        nodes = sorted(topology.nodes.values(), key=lambda item: item.id)
        positions = {
            node.id: (
                margin + (index % 3) * (node_width + horizontal_gap),
                margin + (index // 3) * (node_height + vertical_gap),
            )
            for index, node in enumerate(nodes)
        }
        rows = max(1, (len(nodes) + 2) // 3)
        width = margin * 2 + min(3, max(1, len(nodes))) * node_width
        width += max(0, min(3, len(nodes)) - 1) * horizontal_gap
        height = margin * 2 + rows * node_height + max(0, rows - 1) * vertical_gap
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
                f'height="{height}" viewBox="0 0 {width} {height}" '
                'role="img" aria-label="ChokePoint dependency graph">'
            ),
            "<defs>",
            '<marker id="arrow" markerWidth="10" markerHeight="8" refX="9" '
            'refY="4" orient="auto" markerUnits="strokeWidth">',
            '<path d="M0,0 L10,4 L0,8 Z" fill="#555"/>',
            "</marker>",
            "</defs>",
            '<rect width="100%" height="100%" fill="#ffffff"/>',
        ]
        for edge in sorted(
            topology.edges,
            key=lambda item: (item.source, item.target, item.relationship.value),
        ):
            source = positions[edge.source]
            target = positions[edge.target]
            x1 = source[0] + node_width
            y1 = source[1] + node_height / 2
            x2 = target[0]
            y2 = target[1] + node_height / 2
            lines.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                'stroke="#555" stroke-width="1.5" marker-end="url(#arrow)"/>'
            )
        for node in nodes:
            x, y = positions[node.id]
            label = html.escape(node.name)
            node_type = html.escape(node.node_type.value)
            lines.extend(
                [
                    f'<rect x="{x}" y="{y}" width="{node_width}" '
                    f'height="{node_height}" rx="6" fill="#f8fafc" '
                    'stroke="#334155" stroke-width="1.2"/>',
                    f'<text x="{x + 12}" y="{y + 21}" fill="#0f172a" '
                    'font-family="Arial, sans-serif" font-size="14" '
                    f'font-weight="700">{label}</text>',
                    f'<text x="{x + 12}" y="{y + 38}" fill="#475569" '
                    'font-family="Arial, sans-serif" font-size="11">'
                    f"{node_type}</text>",
                ]
            )
        lines.append("</svg>")
        return "\n".join(lines) + "\n"


def export_csv(topology: Topology) -> str:
    """Export topology dependencies as CSV."""
    return ReportExporter().csv(topology)


def export_mermaid(topology: Topology) -> str:
    """Export topology dependencies as Mermaid."""
    return ReportExporter().mermaid(topology)


def export_svg(topology: Topology) -> str:
    """Export topology dependencies as SVG."""
    return ReportExporter().svg(topology)


def _mermaid_id(value: str) -> str:
    return "n_" + "".join(
        character if character.isalnum() else "_" for character in value
    )


def _escape_mermaid(value: str) -> str:
    return value.replace('"', '\\"')

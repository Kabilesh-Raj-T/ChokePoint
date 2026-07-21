"""Security report and topology export formats."""

from __future__ import annotations

import csv
import html
import io
from dataclasses import dataclass

from blastradius.models import Edge, Node, Topology
from blastradius.utils.text import escape_mermaid_label, mermaid_node_id

SVG_COLUMNS = 3
SVG_NODE_WIDTH = 180
SVG_NODE_HEIGHT = 48
SVG_HORIZONTAL_GAP = 80
SVG_VERTICAL_GAP = 28
SVG_MARGIN = 24
SVG_LABEL_X_OFFSET = 12
SVG_TITLE_Y_OFFSET = 21
SVG_TYPE_Y_OFFSET = 38

Position = tuple[int, int]


@dataclass(frozen=True)
class SvgCanvas:
    """Calculated SVG canvas dimensions."""

    width: int
    height: int


class ReportExporter:
    """Export BlastRadius data to integration-friendly formats."""

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
            lines.append(
                f'  {mermaid_node_id(node.id)}["{escape_mermaid_label(node.name)}"]'
            )
        for edge in sorted(
            topology.edges,
            key=lambda item: (item.source, item.target, item.relationship.value),
        ):
            lines.append(
                "  "
                f"{mermaid_node_id(edge.source)} -->|{edge.relationship.value}| "
                f"{mermaid_node_id(edge.target)}"
            )
        return "\n".join(lines) + "\n"

    def svg(self, topology: Topology) -> str:
        """Export topology as a dependency graph SVG."""
        nodes = sorted(topology.nodes.values(), key=lambda item: item.id)
        positions = _svg_positions(nodes)
        canvas = _svg_canvas(len(nodes))
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas.width}" '
                f'height="{canvas.height}" '
                f'viewBox="0 0 {canvas.width} {canvas.height}" '
                'role="img" aria-label="BlastRadius dependency graph">'
            ),
            *_svg_defs(),
            '<rect width="100%" height="100%" fill="#ffffff"/>',
        ]
        for edge in sorted(
            topology.edges,
            key=lambda item: (item.source, item.target, item.relationship.value),
        ):
            lines.append(_svg_edge(edge, positions))
        for node in nodes:
            lines.extend(_svg_node(node, positions[node.id]))
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


def _svg_positions(nodes: list[Node]) -> dict[str, Position]:
    """Return deterministic SVG node positions."""
    return {
        node.id: (
            SVG_MARGIN + (index % SVG_COLUMNS) * (SVG_NODE_WIDTH + SVG_HORIZONTAL_GAP),
            SVG_MARGIN + (index // SVG_COLUMNS) * (SVG_NODE_HEIGHT + SVG_VERTICAL_GAP),
        )
        for index, node in enumerate(nodes)
    }


def _svg_canvas(node_count: int) -> SvgCanvas:
    """Return SVG canvas dimensions for a node count."""
    rows = max(1, (node_count + SVG_COLUMNS - 1) // SVG_COLUMNS)
    columns = min(SVG_COLUMNS, max(1, node_count))
    width = SVG_MARGIN * 2 + columns * SVG_NODE_WIDTH
    width += max(0, columns - 1) * SVG_HORIZONTAL_GAP
    height = SVG_MARGIN * 2 + rows * SVG_NODE_HEIGHT
    height += max(0, rows - 1) * SVG_VERTICAL_GAP
    return SvgCanvas(width=width, height=height)


def _svg_defs() -> list[str]:
    """Return reusable SVG definitions."""
    return [
        "<defs>",
        '<marker id="arrow" markerWidth="10" markerHeight="8" refX="9" '
        'refY="4" orient="auto" markerUnits="strokeWidth">',
        '<path d="M0,0 L10,4 L0,8 Z" fill="#555"/>',
        "</marker>",
        "</defs>",
    ]


def _svg_edge(edge: Edge, positions: dict[str, Position]) -> str:
    """Render a dependency edge as SVG."""
    source = positions[edge.source]
    target = positions[edge.target]
    x1 = source[0] + SVG_NODE_WIDTH
    y1 = source[1] + SVG_NODE_HEIGHT / 2
    x2 = target[0]
    y2 = target[1] + SVG_NODE_HEIGHT / 2
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        'stroke="#555" stroke-width="1.5" marker-end="url(#arrow)"/>'
    )


def _svg_node(node: Node, position: Position) -> list[str]:
    """Render a topology node as SVG."""
    x, y = position
    label = html.escape(node.name)
    node_type = html.escape(node.node_type.value)
    return [
        f'<rect x="{x}" y="{y}" width="{SVG_NODE_WIDTH}" '
        f'height="{SVG_NODE_HEIGHT}" rx="6" fill="#f8fafc" '
        'stroke="#334155" stroke-width="1.2"/>',
        f'<text x="{x + SVG_LABEL_X_OFFSET}" y="{y + SVG_TITLE_Y_OFFSET}" '
        'fill="#0f172a" font-family="Arial, sans-serif" font-size="14" '
        f'font-weight="700">{label}</text>',
        f'<text x="{x + SVG_LABEL_X_OFFSET}" y="{y + SVG_TYPE_Y_OFFSET}" '
        'fill="#475569" font-family="Arial, sans-serif" font-size="11">'
        f"{node_type}</text>",
    ]

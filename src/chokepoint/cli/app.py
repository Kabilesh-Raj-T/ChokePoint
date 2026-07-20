"""Click command-line interface for ChokePoint."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import NoReturn

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from chokepoint.graph import GraphAnalyzer, GraphBuilder, TopologyDiff, diff_topologies
from chokepoint.graph.engine import AnalysisReport
from chokepoint.models import Topology
from chokepoint.parser import (
    RepositoryScanResult,
    TopologyParseError,
    parse_topology_yaml_file,
    scan_repository,
)
from chokepoint.report import (
    GeneratedReport,
    export_csv,
    export_mermaid,
    generate_security_report,
)

LOGGER = logging.getLogger("chokepoint")
console = Console()
error_console = Console(stderr=True)


class CliContext:
    """Runtime context shared by CLI commands."""

    def __init__(self, *, verbose: bool) -> None:
        """Create CLI context.

        Args:
            verbose: Whether verbose logging and exception details are enabled.
        """
        self.verbose = verbose


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--verbose", is_flag=True, help="Enable verbose colored logs.")
@click.pass_context
def cli(ctx: click.Context, *, verbose: bool) -> None:
    """Analyze infrastructure dependency choke points."""
    _configure_logging(verbose)
    ctx.obj = CliContext(verbose=verbose)
    if verbose:
        LOGGER.debug("Verbose logging enabled")


@cli.command()
@click.argument(
    "topology_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--json", "as_json", is_flag=True, help="Emit structured JSON.")
@click.option("--markdown", is_flag=True, help="Emit Markdown.")
@click.pass_obj
def analyze(
    ctx: CliContext,
    topology_path: Path,
    *,
    as_json: bool,
    markdown: bool,
) -> None:
    """Analyze topology.yaml and print a risk summary."""
    try:
        quiet = as_json
        topology = _load_topology(topology_path, quiet=quiet)
        generated_report = _security_report(topology, quiet=quiet)
    except Exception as error:
        _fail(error, verbose=ctx.verbose)

    _emit_security_report(
        generated_report,
        as_json=as_json,
        markdown=markdown,
    )


@cli.command()
@click.argument(
    "topology_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--json", "as_json", is_flag=True, help="Emit graph metrics as JSON.")
@click.option("--markdown", is_flag=True, help="Emit Markdown graph summary.")
@click.pass_obj
def graph(
    ctx: CliContext,
    topology_path: Path,
    *,
    as_json: bool,
    markdown: bool,
) -> None:
    """Inspect or render the topology graph."""
    try:
        topology = _load_topology(topology_path, quiet=as_json)
        graph_model = GraphBuilder().build(topology)
        analysis = GraphAnalyzer().analyze(graph_model)
    except Exception as error:
        _fail(error, verbose=ctx.verbose)

    if as_json:
        click.echo(analysis.model_dump_json())
    elif markdown:
        console.print(Markdown(_graph_markdown(analysis)))
    else:
        table = Table(title="Graph Summary")
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="green")
        table.add_row("Nodes", str(analysis.node_count))
        table.add_row("Edges", str(analysis.edge_count))
        table.add_row("Connected", str(analysis.is_connected))
        table.add_row("Articulation points", str(len(analysis.articulation_points)))
        table.add_row("Bridges", str(len(analysis.bridges)))
        table.add_row("Cycles", str(len(analysis.cycles)))
        console.print(table)


@cli.command()
@click.argument(
    "topology_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--json", "as_json", is_flag=True, help="Emit structured JSON.")
@click.option("--markdown", is_flag=True, help="Emit Markdown.")
@click.pass_obj
def report(
    ctx: CliContext,
    topology_path: Path,
    *,
    as_json: bool,
    markdown: bool,
) -> None:
    """Generate a risk report for topology.yaml."""
    try:
        quiet = as_json
        topology = _load_topology(topology_path, quiet=quiet)
        generated_report = _security_report(topology, quiet=quiet)
    except Exception as error:
        _fail(error, verbose=ctx.verbose)

    _emit_security_report(
        generated_report,
        as_json=as_json,
        markdown=markdown,
    )


@cli.command()
@click.argument(
    "topology_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--format",
    "export_format",
    type=click.Choice(["csv", "mermaid"]),
    required=True,
    help="Export format.",
)
@click.pass_obj
def export(ctx: CliContext, topology_path: Path, *, export_format: str) -> None:
    """Export topology or report artifacts."""
    try:
        topology = _load_topology(topology_path, quiet=True)
        if export_format == "csv":
            click.echo(export_csv(topology), nl=False)
        else:
            click.echo(export_mermaid(topology), nl=False)
    except Exception as error:
        _fail(error, verbose=ctx.verbose)


@cli.command()
@click.argument(
    "before_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.argument(
    "after_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--json", "as_json", is_flag=True, help="Emit structured JSON.")
@click.pass_obj
def diff(
    ctx: CliContext,
    before_path: Path,
    after_path: Path,
    *,
    as_json: bool,
) -> None:
    """Diff two topology.yaml files."""
    try:
        before = _load_topology(before_path, quiet=True)
        after = _load_topology(after_path, quiet=True)
        topology_diff = diff_topologies(before, after)
    except Exception as error:
        _fail(error, verbose=ctx.verbose)

    if as_json:
        click.echo(topology_diff.model_dump_json(indent=2))
    else:
        click.echo(_diff_markdown(topology_diff))


@cli.command()
@click.argument(
    "topology_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--json", "as_json", is_flag=True, help="Emit validation JSON.")
@click.pass_obj
def validate(ctx: CliContext, topology_path: Path, *, as_json: bool) -> None:
    """Validate topology.yaml."""
    try:
        topology = _load_topology(topology_path, quiet=as_json)
    except Exception as error:
        if as_json:
            console.print_json(json.dumps({"valid": False, "error": str(error)}))
            raise click.exceptions.Exit(1) from error
        _fail(error, verbose=ctx.verbose)

    payload = {
        "valid": True,
        "nodes": len(topology.nodes),
        "edges": len(topology.edges),
    }
    if as_json:
        click.echo(json.dumps(payload))
    else:
        console.print(
            f"[bold green]Valid topology[/]: "
            f"{payload['nodes']} node(s), {payload['edges']} edge(s)"
        )


@cli.command()
@click.argument(
    "repo_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--json", "as_json", is_flag=True, help="Emit structured JSON.")
@click.option("--markdown", is_flag=True, help="Emit Markdown.")
@click.pass_obj
def scan(
    ctx: CliContext,
    repo_path: Path,
    *,
    as_json: bool,
    markdown: bool,
) -> None:
    """Scan a repository for supported infrastructure files."""
    try:
        quiet = as_json or markdown
        scan_result = _scan_repository(repo_path, quiet=quiet)
        generated_report = generate_security_report(scan_result.topology)
    except Exception as error:
        _fail(error, verbose=ctx.verbose)

    if as_json:
        click.echo(_scan_json(scan_result, generated_report))
    elif markdown:
        click.echo(_scan_markdown(scan_result, generated_report))
    else:
        _emit_scan_terminal(scan_result, generated_report)


def main() -> None:
    """Run the ChokePoint CLI."""
    cli()


def _load_topology(path: Path, *, quiet: bool) -> Topology:
    """Load a topology with progress output."""
    if quiet:
        return parse_topology_yaml_file(path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task(f"Parsing {path.name}", total=None)
        topology = parse_topology_yaml_file(path)
    LOGGER.info(
        "Loaded topology with %s nodes and %s edges",
        len(topology.nodes),
        len(topology.edges),
    )
    return topology


def _security_report(topology: Topology, *, quiet: bool) -> GeneratedReport:
    """Generate a security report with progress output."""
    if quiet:
        return generate_security_report(topology)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("Generating security report", total=None)
        return generate_security_report(topology)


def _scan_repository(path: Path, *, quiet: bool) -> RepositoryScanResult:
    """Scan a repository with progress output."""
    if quiet:
        return scan_repository(path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task(f"Scanning {path.name}", total=None)
        result = scan_repository(path)
    LOGGER.info(
        "Scanned repository with %s artifact(s), %s issue(s), %s node(s), %s edge(s)",
        len(result.artifacts),
        len(result.issues),
        len(result.topology.nodes),
        len(result.topology.edges),
    )
    return result


def _emit_security_report(
    report: GeneratedReport,
    *,
    as_json: bool,
    markdown: bool,
) -> None:
    """Emit a security report in the requested format."""
    if as_json:
        click.echo(report.to_json())
    elif markdown:
        click.echo(report.to_markdown())
    else:
        console.print(report.to_terminal())


def _emit_scan_terminal(
    scan_result: RepositoryScanResult,
    report: GeneratedReport,
) -> None:
    """Emit repository scan summary and report to the terminal."""
    summary = Table(title="Repository Scan")
    summary.add_column("Metric", style="bold cyan")
    summary.add_column("Value", style="green")
    summary.add_row("Root", scan_result.root)
    summary.add_row("Artifacts", str(len(scan_result.artifacts)))
    summary.add_row("Issues", str(len(scan_result.issues)))
    summary.add_row("Nodes", str(len(scan_result.topology.nodes)))
    summary.add_row("Edges", str(len(scan_result.topology.edges)))
    console.print(summary)

    artifacts = Table(title="Parsed Artifacts")
    artifacts.add_column("Kind")
    artifacts.add_column("Path")
    artifacts.add_column("Nodes", justify="right")
    artifacts.add_column("Edges", justify="right")
    if not scan_result.artifacts:
        artifacts.add_row("none", "No supported infrastructure files found", "0", "0")
    for artifact in scan_result.artifacts:
        artifacts.add_row(
            artifact.kind,
            artifact.path,
            str(artifact.nodes),
            str(artifact.edges),
        )
    console.print(artifacts)

    if scan_result.issues:
        issues = Table(title="Skipped Artifacts")
        issues.add_column("Kind")
        issues.add_column("Path")
        issues.add_column("Error")
        for issue in scan_result.issues:
            issues.add_row(issue.kind, issue.path, issue.error)
        console.print(issues)

    if scan_result.topology.nodes:
        console.print(report.to_terminal())


def _scan_json(scan_result: RepositoryScanResult, report: GeneratedReport) -> str:
    """Return repository scan JSON."""
    payload = {
        "root": scan_result.root,
        "artifact_count": len(scan_result.artifacts),
        "issue_count": len(scan_result.issues),
        "nodes": len(scan_result.topology.nodes),
        "edges": len(scan_result.topology.edges),
        "artifacts": [
            artifact.model_dump(mode="json") for artifact in scan_result.artifacts
        ],
        "issues": [issue.model_dump(mode="json") for issue in scan_result.issues],
        "report": json.loads(report.to_json()),
    }
    return json.dumps(payload, indent=2)


def _scan_markdown(scan_result: RepositoryScanResult, report: GeneratedReport) -> str:
    """Return repository scan Markdown."""
    lines = [
        "# ChokePoint Repository Scan",
        "",
        f"- Root: `{scan_result.root}`",
        f"- Parsed artifacts: `{len(scan_result.artifacts)}`",
        f"- Skipped artifacts: `{len(scan_result.issues)}`",
        f"- Nodes: `{len(scan_result.topology.nodes)}`",
        f"- Edges: `{len(scan_result.topology.edges)}`",
        "",
        "## Parsed Artifacts",
        "",
        *_scan_artifacts_markdown(scan_result),
        "",
        "## Skipped Artifacts",
        "",
        *_scan_issues_markdown(scan_result),
        "",
        report.to_markdown(),
    ]
    return "\n".join(lines)


def _scan_artifacts_markdown(scan_result: RepositoryScanResult) -> list[str]:
    """Render repository scan artifacts as Markdown."""
    if not scan_result.artifacts:
        return ["No supported infrastructure files found."]
    lines = [
        "| Kind | Path | Nodes | Edges |",
        "| --- | --- | ---: | ---: |",
    ]
    for artifact in scan_result.artifacts:
        lines.append(
            f"| `{artifact.kind}` | `{artifact.path}` | "
            f"{artifact.nodes} | {artifact.edges} |"
        )
    return lines


def _scan_issues_markdown(scan_result: RepositoryScanResult) -> list[str]:
    """Render repository scan issues as Markdown."""
    if not scan_result.issues:
        return ["None."]
    return [
        f"- `{issue.kind}` `{issue.path}`: {issue.error}"
        for issue in scan_result.issues
    ]


def _graph_markdown(analysis: AnalysisReport) -> str:
    """Return a Markdown graph summary."""
    return "\n".join(
        [
            "# ChokePoint Graph Summary",
            "",
            f"- Nodes: `{analysis.node_count}`",
            f"- Edges: `{analysis.edge_count}`",
            f"- Connected: `{analysis.is_connected}`",
            f"- Articulation points: `{', '.join(analysis.articulation_points)}`",
            f"- Bridges: `{len(analysis.bridges)}`",
            f"- Cycles: `{len(analysis.cycles)}`",
        ]
    )


def _diff_markdown(diff: TopologyDiff) -> str:
    """Return a Markdown topology diff summary."""
    return "\n".join(
        [
            "# ChokePoint Topology Diff",
            "",
            f"- Added nodes: `{len(diff.added_nodes)}`",
            f"- Removed nodes: `{len(diff.removed_nodes)}`",
            f"- Changed nodes: `{len(diff.changed_nodes)}`",
            f"- Added edges: `{len(diff.added_edges)}`",
            f"- Removed edges: `{len(diff.removed_edges)}`",
        ]
    )


def _configure_logging(verbose: bool) -> None:
    """Configure colored CLI logging."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=error_console, rich_tracebacks=verbose)],
        force=True,
    )


def _fail(error: Exception, *, verbose: bool) -> NoReturn:
    """Render a helpful CLI error and exit."""
    if verbose:
        LOGGER.exception("Command failed")
    if isinstance(error, TopologyParseError | ValueError):
        raise click.ClickException(str(error)) from error
    raise click.ClickException(f"unexpected error: {error}") from error

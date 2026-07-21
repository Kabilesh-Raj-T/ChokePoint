"""End-to-end checks for checked-in example topologies."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from blastradius.cli import cli
from blastradius.parser import parse_topology_yaml_file

EXAMPLE_PATHS = tuple(sorted(Path("examples").glob("topology-*.yaml")))


@pytest.mark.parametrize("path", EXAMPLE_PATHS, ids=lambda path: path.name)
def test_example_topology_parses(path: Path) -> None:
    topology = parse_topology_yaml_file(path)

    assert topology.nodes


@pytest.mark.parametrize("path", EXAMPLE_PATHS, ids=lambda path: path.name)
@pytest.mark.parametrize(
    "arguments, expected_output",
    (
        (("validate", "{path}", "--json"), '"valid": true'),
        (("analyze", "{path}", "--json"), '"title": "BlastRadius Security Report"'),
        (("graph", "{path}", "--json"), '"node_count"'),
        (("report", "{path}", "--markdown"), "# BlastRadius Security Report"),
    ),
)
def test_example_topology_cli_commands(
    path: Path,
    arguments: tuple[str, ...],
    expected_output: str,
) -> None:
    command = [argument.format(path=str(path)) for argument in arguments]

    result = CliRunner().invoke(cli, command)

    assert result.exit_code == 0
    assert expected_output in result.output

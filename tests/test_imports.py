"""Import tests for the BlastRadius package structure."""

import importlib
from collections.abc import Iterable


def test_package_modules_are_importable() -> None:
    """Verify that each public package boundary can be imported."""
    module_names: Iterable[str] = (
        "blastradius",
        "blastradius.__main__",
        "blastradius.cli",
        "blastradius.graph",
        "blastradius.models",
        "blastradius.parser",
        "blastradius.report",
        "blastradius.utils",
        "blastradius.visualization",
    )

    for module_name in module_names:
        assert importlib.import_module(module_name).__name__ == module_name

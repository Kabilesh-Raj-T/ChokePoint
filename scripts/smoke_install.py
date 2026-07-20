"""Smoke-test ChokePoint installation modes in isolated virtual environments."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    """Install ChokePoint and verify package entry points."""
    args = _parse_args()
    root = Path.cwd()
    if args.editable:
        _smoke_install(root, ["-e", str(root)])
    if args.wheel:
        _smoke_install(root, [str(_single_artifact(root / "dist", "*.whl"))])
    if args.sdist:
        _smoke_install(root, [str(_single_artifact(root / "dist", "*.tar.gz"))])


def _parse_args() -> argparse.Namespace:
    """Parse smoke-test mode flags."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--editable", action="store_true", help="Test pip install -e .")
    parser.add_argument(
        "--wheel", action="store_true", help="Test built wheel install."
    )
    parser.add_argument(
        "--sdist", action="store_true", help="Test built sdist install."
    )
    args = parser.parse_args()
    if not (args.editable or args.wheel or args.sdist):
        args.wheel = True
    return args


def _smoke_install(root: Path, install_args: list[str]) -> None:
    """Install ChokePoint into a temp venv and verify entry points."""
    with tempfile.TemporaryDirectory(prefix="chokepoint-install-smoke-") as temp_dir:
        venv = Path(temp_dir) / ".venv"
        python = _venv_python(venv)
        console_script = _venv_script(venv, "chokepoint")

        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        subprocess.run(
            [str(python), "-m", "pip", "install", "--upgrade", "pip"],
            check=True,
        )
        subprocess.run([str(python), "-m", "pip", "install", *install_args], check=True)
        subprocess.run(
            [
                str(python),
                "-m",
                "chokepoint",
                "validate",
                "examples/basic.yaml",
            ],
            check=True,
        )
        subprocess.run([str(console_script), "--help"], check=True)


def _single_artifact(dist_dir: Path, pattern: str) -> Path:
    """Return the single artifact matching a pattern in a distribution directory."""
    artifacts = sorted(dist_dir.glob(pattern))
    if len(artifacts) != 1:
        message = (
            f"expected exactly one {pattern} artifact in {dist_dir}, "
            f"found {len(artifacts)}"
        )
        raise RuntimeError(message)
    return artifacts[0]


def _venv_python(venv: Path) -> Path:
    """Return the Python executable path for the current platform."""
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    return venv / scripts_dir / executable


def _venv_script(venv: Path, name: str) -> Path:
    """Return a console-script path for the current platform."""
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable = f"{name}.exe" if os.name == "nt" else name
    return venv / scripts_dir / executable


if __name__ == "__main__":
    main()

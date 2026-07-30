#!/usr/bin/env python3
"""Verify that every public console entry point loads from an installed wheel."""

from importlib.metadata import distribution
from pathlib import Path
import subprocess
import sys

EXPECTED_ENTRY_POINTS = {
    "mcp-kicad": "mcp_kicad.server.extended:main",
    "mcp-kicad-basic": "mcp_kicad.server.basic:main",
    "mcp-kicad-client": "mcp_kicad.client.claude:main",
}


def main() -> None:
    entry_points = {
        entry_point.name: entry_point
        for entry_point in distribution("mcp-kicad").entry_points
        if entry_point.group == "console_scripts"
    }

    missing = EXPECTED_ENTRY_POINTS.keys() - entry_points.keys()
    if missing:
        raise RuntimeError(f"Missing console entry points: {sorted(missing)}")

    for name, expected_value in EXPECTED_ENTRY_POINTS.items():
        entry_point = entry_points[name]
        if entry_point.value != expected_value:
            raise RuntimeError(
                f"{name} points to {entry_point.value!r}, expected {expected_value!r}"
            )

        loaded = entry_point.load()
        if not callable(loaded):
            raise TypeError(f"{name} did not load a callable")

        executable = Path(sys.executable).with_name(name)
        result = subprocess.run(
            [str(executable), "--help"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{name} --help failed with {result.returncode}: {result.stderr}"
            )

        print(f"OK {name}: {entry_point.value}")


if __name__ == "__main__":
    main()

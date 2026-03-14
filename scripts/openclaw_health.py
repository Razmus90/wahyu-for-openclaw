#!/usr/bin/env python3
"""Inspect OpenClaw runtime health (config, directories, Python scripts)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class PathHealth:
    path: Path
    is_dir: bool
    size: int
    modified_at: datetime

    def summary(self) -> str:
        kind = "dir " if self.is_dir else "file"
        size_desc = f"{self.size:,} bytes" if not self.is_dir else "-"
        return f"{kind:<4} {self.path.name:<20} {size_desc:<15} {self.modified_at:%Y-%m-%d %H:%M:%S}"


def collect_health(paths: Iterable[Path]) -> List[PathHealth]:
    health = []
    for path in sorted(paths):
        try:
            stat = path.stat()
        except (PermissionError, FileNotFoundError):
            continue
        health.append(
            PathHealth(
                path=path,
                is_dir=path.is_dir(),
                size=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )
        )
    return health


def format_config_status(config_path: Path) -> str:
    if not config_path.exists():
        return "missing"
    size = config_path.stat().st_size
    if size == 0:
        return "exists but empty"
    return f"{size:,} bytes"


def find_python_scripts(root: Path, extra_roots: Sequence[Path]) -> List[Path]:
    visited = set()
    scripts = []
    for point in (root, *extra_roots):
        if not point.exists():
            continue
        for path in point.rglob("*.py"):
            if path in visited:
                continue
            visited.add(path)
            scripts.append(path)
    return sorted(scripts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report health of the local OpenClaw installation and Python scripts."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.home() / ".openclaw",
        help="Root of the OpenClaw install (default: ~/.openclaw)",
    )
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    print(f"Inspecting OpenClaw root: {root}")

    top_level = [entry for entry in root.iterdir() if entry.name[0] != "~"] if root.exists() else []
    health = collect_health(top_level)
    print("\nDirectory health for top-level entries:")
    print("Kind Name                 Size            Modified")
    for entry in health:
        print(entry.summary())

    config_path = root / "config.yaml"
    config_status = format_config_status(config_path)
    print(f"\nconfig.yaml status: {config_status}")

    workspace = root / "workspace"
    scripts = find_python_scripts(root, [workspace])
    print(f"\nFound {len(scripts)} Python script(s):")
    for script in scripts:
        print(f" - {script.relative_to(root)}")

    if not scripts:
        print("No Python scripts found under the root/workspace paths.")


if __name__ == "__main__":
    main()

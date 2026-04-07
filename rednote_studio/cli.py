from __future__ import annotations

import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rednote_studio",
        description="Utilities for managing a Rednote video production project.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("info", help="Show project paths.")
    subparsers.add_parser(
        "init-workspace",
        help="Create common directories for scripts and outputs.",
    )

    return parser


def cmd_info() -> int:
    print(f"project_root: {PROJECT_ROOT}")
    print(f"data_dir: {DATA_DIR}")
    print(f"output_dir: {OUTPUT_DIR}")
    print(f"scripts_dir: {SCRIPTS_DIR}")
    return 0


def cmd_init_workspace() -> int:
    for path in (OUTPUT_DIR, SCRIPTS_DIR):
        path.mkdir(parents=True, exist_ok=True)
    print("Workspace initialized.")
    print(f"Created or confirmed: {OUTPUT_DIR}")
    print(f"Created or confirmed: {SCRIPTS_DIR}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "info":
        return cmd_info()
    if args.command == "init-workspace":
        return cmd_init_workspace()

    parser.print_help()
    return 0

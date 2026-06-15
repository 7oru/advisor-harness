"""Command-line interface for Multi-Agent Advisor."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

from packages.harness import __version__
from packages.harness.defaults import init_workspace


def _run_version(command: str) -> str:
    exe = shutil.which(command)
    if not exe:
        return "not found"
    try:
        result = subprocess.run(
            [exe, "--version"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "found, version check failed: {}".format(exc)
    output = (result.stdout or result.stderr).strip()
    return output or "found"


def cmd_doctor(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    print("maa {}".format(__version__))
    print("workspace: {}".format(root))
    print("kimi: {}".format(_run_version("kimi")))
    print("codex: {}".format(_run_version("codex")))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    directories_seen, files_created = init_workspace(root)
    print("initialized workspace: {}".format(root))
    print("directories ensured: {}".format(directories_seen))
    print("default files created: {}".format(files_created))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maa", description="Multi-Agent Advisor harness")
    parser.add_argument("--version", action="version", version="maa {}".format(__version__))
    parser.add_argument(
        "--cwd",
        default=".",
        help="Workspace root for commands that read or write local artifacts.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Check local CLI dependencies")
    doctor_parser.set_defaults(func=cmd_doctor)

    init_parser = subparsers.add_parser("init", help="Create local workspace directories and defaults")
    init_parser.set_defaults(func=cmd_init)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

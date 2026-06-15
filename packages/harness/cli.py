"""Command-line interface for Multi-Agent Advisor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Optional

from packages.adapters import CodexCliAdapter, KimiCliAdapter
from packages.harness import __version__
from packages.harness.defaults import init_workspace
from packages.harness.runner import run_task
from packages.harness.security_questionnaire import run_security_questionnaire


def cmd_doctor(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    print("maa {}".format(__version__))
    print("workspace: {}".format(root))
    print("kimi: {}".format(KimiCliAdapter.version()))
    print("codex: {}".format(CodexCliAdapter.version()))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    directories_seen, files_created = init_workspace(root)
    print("initialized workspace: {}".format(root))
    print("directories ensured: {}".format(directories_seen))
    print("default files created: {}".format(files_created))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    task = " ".join(args.task).strip()
    result = run_task(
        root=root,
        task=task,
        executor_backend=args.executor,
        advisor_backend=args.advisor,
        timeout_seconds=args.timeout,
    )
    print("run_id: {}".format(result.run_id))
    print("run_dir: {}".format(result.run_dir))
    print("status: {}".format(result.outcome["status"]))
    print("advisor_requests: {}".format(result.outcome["advice_request_count"]))
    print("memory_proposals: {}".format(result.outcome["memory_proposal_count"]))
    return 0 if result.outcome["status"] == "completed" else 1


def cmd_run_security_questionnaire(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    result = run_security_questionnaire(
        root=root,
        questionnaire=Path(args.questionnaire),
        knowledge=Path(args.knowledge),
        executor_backend=args.executor,
        advisor_backend=args.advisor,
        timeout_seconds=args.timeout,
    )
    print("run_id: {}".format(result.run_id))
    print("run_dir: {}".format(result.run_dir))
    print("status: {}".format(result.outcome["status"]))
    print("answers_draft: {}".format(result.run_dir / "answers_draft.md"))
    print("risk_flags: {}".format(result.run_dir / "risk_flags.md"))
    return 0 if result.outcome["status"] == "completed" else 1


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

    run_parser = subparsers.add_parser("run", help="Run a generic advisor harness task")
    run_parser.add_argument("task", nargs="+", help="Task description")
    run_parser.add_argument("--executor", default="kimi", choices=["kimi", "codex", "fake"])
    run_parser.add_argument("--advisor", default="codex", choices=["kimi", "codex", "fake"])
    run_parser.add_argument("--timeout", default=240, type=int, help="Per-agent timeout in seconds")
    run_parser.set_defaults(func=cmd_run)

    sq_parser = subparsers.add_parser(
        "run-security-questionnaire",
        help="Run the security questionnaire workflow scaffold",
    )
    sq_parser.add_argument("questionnaire", help="Questionnaire file path")
    sq_parser.add_argument("--knowledge", required=True, help="Local knowledge file or directory")
    sq_parser.add_argument("--executor", default="kimi", choices=["kimi", "codex", "fake"])
    sq_parser.add_argument("--advisor", default="codex", choices=["kimi", "codex", "fake"])
    sq_parser.add_argument("--timeout", default=240, type=int, help="Per-agent timeout in seconds")
    sq_parser.set_defaults(func=cmd_run_security_questionnaire)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

"""Command-line interface for Multi-Agent Advisor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Optional

from packages.adapters import CodexCliAdapter, KimiCliAdapter
from packages.harness import __version__
from packages.harness.defaults import init_workspace
from packages.harness.evaluation import run_evaluation
from packages.harness.review import review_run
from packages.harness.runner import run_task


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
        max_turns=args.max_turns,
        max_advisor_calls=args.max_advisor_calls,
    )
    print("run_id: {}".format(result.run_id))
    print("run_dir: {}".format(result.run_dir))
    print("status: {}".format(result.outcome["status"]))
    print("advisor_consults: {}".format(result.outcome["advisor_consult_count"]))
    print("memory_proposals: {}".format(result.outcome["memory_proposal_count"]))
    return 0 if result.outcome["status"] == "completed" else 1


def cmd_review(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    outcome = review_run(
        root=root,
        run_id=args.run,
        advisor_backend=args.advisor,
        timeout_seconds=args.timeout,
    )
    run_dir = root / "runs" / args.run
    print("run_id: {}".format(args.run))
    print("run_dir: {}".format(run_dir))
    print("status: {}".format(outcome["status"]))
    print("post_run_review: {}".format(run_dir / "post_run_review.md"))
    print("policy_patch_proposal: {}".format(run_dir / "policy_patch_proposal.md"))
    return 0 if outcome["status"] == "completed" else 1


def cmd_eval(args: argparse.Namespace) -> int:
    root = Path(args.cwd).resolve()
    result = run_evaluation(
        root=root,
        include_live=args.include_live,
        live_executor=args.live_executor,
        live_advisor=args.live_advisor,
        live_timeout_seconds=args.live_timeout,
    )
    summary = result["summary"]
    print("evaluation_id: {}".format(summary["evaluation_id"]))
    print("eval_dir: {}".format(result["eval_dir"]))
    print("verdict: {}".format(summary["verdict"]))
    print("passed: {}/{}".format(summary["passed_count"], summary["scenario_count"]))
    print("pass_rate: {:.3f}".format(summary["metrics"].get("pass_rate", 0.0)))
    return 0 if summary["failed_count"] == 0 else 1


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
    run_parser.add_argument("--max-turns", default=3, type=int, help="Maximum executor turns")
    run_parser.add_argument("--max-advisor-calls", default=3, type=int, help="Maximum advisor consultations")
    run_parser.set_defaults(func=cmd_run)

    review_parser = subparsers.add_parser("review", help="Run advisor post-run review")
    review_parser.add_argument("--run", required=True, help="Run id to review")
    review_parser.add_argument("--advisor", default="codex", choices=["kimi", "codex", "fake"])
    review_parser.add_argument("--timeout", default=240, type=int, help="Advisor timeout in seconds")
    review_parser.set_defaults(func=cmd_review)

    eval_parser = subparsers.add_parser("eval", help="Run scaffold evaluation and regression scenarios")
    eval_parser.add_argument("--include-live", action="store_true", help="Include one live Kimi/Codex smoke scenario")
    eval_parser.add_argument("--live-executor", default="kimi", choices=["kimi", "codex", "fake"])
    eval_parser.add_argument("--live-advisor", default="codex", choices=["kimi", "codex", "fake"])
    eval_parser.add_argument("--live-timeout", default=240, type=int, help="Per-agent timeout for live scenarios")
    eval_parser.set_defaults(func=cmd_eval)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

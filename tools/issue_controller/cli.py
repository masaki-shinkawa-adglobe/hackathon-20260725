from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .config import load_config
from .controller import Controller


def _issue_selection(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--issue", type=int, action="append")
    group.add_argument("--auto", action="store_true")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="issue-controller")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/issue-controller.toml"),
    )
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor")
    plan = subcommands.add_parser("plan")
    _issue_selection(plan)
    start = subcommands.add_parser("start")
    _issue_selection(start)
    start.add_argument("--no-publish", action="store_true")
    status = subcommands.add_parser("status")
    status.add_argument("--issue", type=int)
    resume = subcommands.add_parser("resume")
    resume.add_argument("--issue", type=int)
    validate = subcommands.add_parser("validate")
    validate.add_argument("--issue", type=int, required=True)
    publish = subcommands.add_parser("publish")
    publish.add_argument("--issue", type=int, required=True)
    merge = subcommands.add_parser("merge")
    merge.add_argument("--issue", type=int, required=True)
    merge.add_argument("--head-sha", required=True)
    cleanup = subcommands.add_parser("cleanup")
    cleanup.add_argument("--issue", type=int, required=True)
    return parser


def _label_names(issue: dict[str, Any]) -> set[str]:
    labels = issue.get("labels") or []
    return {
        str(label.get("name"))
        for label in labels
        if isinstance(label, dict) and isinstance(label.get("name"), str)
    }


def _automatic_issues(controller: Controller) -> list[int]:
    excluded = {
        "status:in-progress",
        "status:review",
        "status:blocked",
        "status:needs-input",
    }
    priorities = {
        "priority:critical": 0,
        "priority:high": 1,
        "priority:medium": 2,
        "priority:low": 3,
    }
    candidates = [
        issue
        for issue in controller.gh.list_issues()
        if not (_label_names(issue) & excluded)
    ]

    def key(issue: dict[str, Any]) -> tuple[int, int]:
        labels = _label_names(issue)
        priority = min(
            (value for label, value in priorities.items() if label in labels),
            default=4,
        )
        return priority, int(issue["number"])

    return [
        int(issue["number"])
        for issue in sorted(candidates, key=key)
    ]


def _numbers(args: argparse.Namespace, controller: Controller) -> list[int]:
    if args.auto:
        numbers = _automatic_issues(controller)
        if not numbers:
            raise RuntimeError("no eligible open Issue")
        return numbers
    return list(args.issue)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        controller = Controller(args.repository, config)
        if args.command == "doctor":
            failures = controller.doctor()
            output: Any = {"ok": not failures, "failures": failures}
            code = 0 if not failures else 1
        elif args.command == "plan":
            output = controller.plan(_numbers(args, controller))
            code = 0
        elif args.command == "start":
            output = controller.start(
                _numbers(args, controller),
                no_publish=args.no_publish,
            )
            code = 0
        elif args.command == "status":
            output = controller.status(args.issue)
            code = 0
        elif args.command == "resume":
            output = controller.resume(args.issue)
            code = 0
        elif args.command == "validate":
            output = controller.validate(args.issue)
            code = 0
        elif args.command == "publish":
            output = controller.publish(args.issue)
            code = 0
        elif args.command == "merge":
            output = controller.merge(args.issue, args.head_sha)
            code = 0
        elif args.command == "cleanup":
            output = controller.cleanup(args.issue)
            code = 0
        else:
            parser.error("unknown command")
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

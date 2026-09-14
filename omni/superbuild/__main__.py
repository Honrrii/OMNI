"""Local operator CLI. There is no provider, scheduler, or promotion command."""
from dataclasses import asdict
import argparse
from pathlib import Path

from omni.superbuild.models import work_from_dict
from omni.superbuild.workspace import SuperBuildBox
from omni.testcube.candidate_models import strict_json
from omni.testcube.collector_models import canonical_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / "omni_superbuild")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    for field in ("project-id", "title", "description", "source-repo", "origin-commit"):
        create.add_argument("--" + field, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("project_id")
    add = commands.add_parser("add-work")
    add.add_argument("--file", type=Path, required=True, help="Operator-owned work-item JSON, never model output")
    advance = commands.add_parser("advance")
    advance.add_argument("project_id")
    advance.add_argument("work_item_id")
    advance.add_argument("status")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("project_id")
    evaluate.add_argument("work_item_id")
    evaluate.add_argument("--patch-a", type=Path, required=True)
    evaluate.add_argument("--patch-b", type=Path, required=True)
    decide = commands.add_parser("decide")
    for field in ("project-id", "work-item-id", "decision", "operator", "parent-checkpoint",
                  "parent-accepted-commit", "evidence-digest"):
        decide.add_argument("--" + field, required=True)
    decide.add_argument("--candidate-digest")
    decide.add_argument("--patch-digest")
    args = vars(parser.parse_args())
    box = SuperBuildBox(args.pop("root"))
    command = args.pop("command")
    if command == "add-work":
        state = box.add_work_item(work_from_dict(strict_json(args["file"].read_bytes())))
    else:
        method = box.load if command == "verify" else getattr(box, command)
        state = method(**args)
    print(canonical_bytes(asdict(state)).decode(), end="")


if __name__ == "__main__":
    main()

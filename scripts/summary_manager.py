#!/usr/bin/env python3
"""
Append tasks to summary.md with dedup check.

Usage:
    python3 summary_manager.py "Task title here" "Another task"
    python3 summary_manager.py --tasks "Task 1|Task 2|Task 3"
    echo "Task 1|Task 2" | python3 summary_manager.py --stdin
"""

import sys
import argparse
from datetime import date
from pathlib import Path

SUMMARY_FILE = Path(__file__).parent.parent / "data" / "summary.md"


def load_existing_tasks() -> set:
    if not SUMMARY_FILE.exists():
        return set()
    tasks = set()
    for line in SUMMARY_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("- [ ] "):
            tasks.add(line[6:].strip().lower())
        elif line.startswith("- [x] "):
            tasks.add(line[6:].strip().lower())
        elif line.startswith("- "):
            tasks.add(line[2:].strip().lower())
    return tasks


def append_tasks(tasks: list) -> dict:
    today = date.today().strftime("%Y-%m-%d")
    existing = load_existing_tasks()

    new_tasks = [t.strip() for t in tasks if t.strip() and t.strip().lower() not in existing]
    skipped = [t.strip() for t in tasks if t.strip() and t.strip().lower() in existing]

    if not new_tasks:
        return {"added": [], "skipped": skipped}

    content = SUMMARY_FILE.read_text() if SUMMARY_FILE.exists() else ""
    if not content.startswith("# Work Summary"):
        content = "# Work Summary\n" + content

    if f"## {today}" in content:
        lines = content.splitlines()
        insert_at = len(lines)
        in_today = False
        for i, line in enumerate(lines):
            if f"## {today}" in line:
                in_today = True
                continue
            if in_today and line.startswith("## "):
                insert_at = i
                break
        for j, task in enumerate(new_tasks):
            lines.insert(insert_at + j, f"- [ ] {task}")
        content = "\n".join(lines) + "\n"
    else:
        section = f"\n## {today}\n" + "".join(f"- [ ] {t}\n" for t in new_tasks)
        content = content.rstrip("\n") + "\n" + section

    SUMMARY_FILE.write_text(content)
    return {"added": new_tasks, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks", nargs="*")
    parser.add_argument("--tasks", dest="tasks_pipe")
    parser.add_argument("--stdin", action="store_true")
    args = parser.parse_args()

    if args.stdin:
        tasks = [t.strip() for t in sys.stdin.read().strip().split("|")]
    elif args.tasks_pipe:
        tasks = [t.strip() for t in args.tasks_pipe.split("|")]
    elif args.tasks:
        tasks = args.tasks
    else:
        parser.print_help()
        sys.exit(1)

    result = append_tasks(tasks)
    for t in result["added"]:
        print(f"✅ Added: {t}")
    for t in result["skipped"]:
        print(f"⏭️  Skip: {t}")
    if not result["added"]:
        print("ℹ️  Nothing new.")


if __name__ == "__main__":
    main()

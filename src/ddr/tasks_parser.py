"""Parse task.md — strips checkbox markers cleanly."""

import re
from pathlib import Path

from . import config

_BULLET_RE = re.compile(r"^-\s+(?:\[[ xX]\]\s+)?")


def strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


def read_tasks_from_file(path: Path | None = None) -> list[str]:
    task_file = path or config.TASK_FILE
    if not task_file.exists():
        raise FileNotFoundError(f"task.md not found at {task_file}")

    tasks: list[str] = []
    in_todo = False
    for raw_line in task_file.read_text().splitlines():
        line = raw_line.strip()
        if re.match(r"^##\s+(todo|tasks)", line, re.IGNORECASE):
            in_todo = True
            continue
        if line.startswith("##"):
            in_todo = False
            continue
        if in_todo and line.startswith("-"):
            task = strip_bullet(line)
            if task:
                tasks.append(task)
    return tasks


def parse_pipe_string(text: str) -> list[str]:
    return [strip_bullet(t) for t in text.split("|") if t.strip()]

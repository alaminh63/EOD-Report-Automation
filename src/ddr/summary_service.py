"""Append tasks to summary.md with correct dedup (fixes C1 bug)."""

from datetime import date

from . import config
from .tasks_parser import strip_bullet


def load_existing_tasks() -> set[str]:
    if not config.SUMMARY_FILE.exists():
        return set()
    tasks: set[str] = set()
    for raw in config.SUMMARY_FILE.read_text().splitlines():
        line = raw.strip()
        if line.startswith("-"):
            task = strip_bullet(line)
            if task:
                tasks.add(task.lower())
    return tasks


def append_tasks(tasks: list[str]) -> dict:
    today = date.today().strftime("%Y-%m-%d")
    existing = load_existing_tasks()

    new_tasks = [t.strip() for t in tasks if t.strip() and t.strip().lower() not in existing]
    skipped = [t.strip() for t in tasks if t.strip() and t.strip().lower() in existing]

    if not new_tasks:
        return {"added": [], "skipped": skipped}

    content = config.SUMMARY_FILE.read_text() if config.SUMMARY_FILE.exists() else ""
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

    config.SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SUMMARY_FILE.write_text(content)
    return {"added": new_tasks, "skipped": skipped}

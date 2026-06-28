"""Orchestrate the full report pipeline: format → doc → pdf → chat."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StepResult:
    ok: bool
    message: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class PipelineResult:
    tasks: list[str] = field(default_factory=list)
    format_step: StepResult | None = None
    doc_step: StepResult | None = None
    pdf_step: StepResult | None = None
    chat_step: StepResult | None = None
    doc_url: str = ""
    pdf_path: str = ""
    pdf_drive_link: str = ""
    day_num: int = 0
    report_date: str = ""

    @property
    def success(self) -> bool:
        steps = [self.doc_step, self.pdf_step]
        return all(s is not None and s.ok for s in steps)

    def to_dict(self) -> dict:
        def step_dict(s: StepResult | None) -> dict:
            if s is None:
                return {"ok": None, "message": ""}
            return {"ok": s.ok, "message": s.message, **s.data}

        return {
            "success": self.success,
            "tasks": self.tasks,
            "doc_url": self.doc_url,
            "pdf_path": self.pdf_path,
            "pdf_drive_link": self.pdf_drive_link,
            "day_num": self.day_num,
            "report_date": self.report_date,
            "steps": {
                "format": step_dict(self.format_step),
                "doc": step_dict(self.doc_step),
                "pdf": step_dict(self.pdf_step),
                "chat": step_dict(self.chat_step),
            },
        }


def run(
    *,
    tasks: list[str] | None = None,
    description: str | None = None,
    task_count: int = 5,
    send_chat: bool = False,
    pdf_path: Path | None = None,
) -> PipelineResult:
    """
    Run the full pipeline.
    Provide either `tasks` (pre-formatted) or `description` (AI formats it).
    """
    from .ai_formatter import format_tasks
    from .chat_service import build_message, send_to_chat
    from .docs_service import update_doc
    from .drive_service import export_pdf, upload_pdf
    from .summary_service import append_tasks
    from .tasks_parser import read_tasks_from_file

    result = PipelineResult()

    # ── Step 1: Resolve tasks ────────────────────────────────────────────────
    if tasks:
        result.tasks = [t.strip() for t in tasks if t.strip()]
        result.format_step = StepResult(ok=True, message=f"{len(result.tasks)} tasks provided")
    elif description:
        try:
            result.tasks = format_tasks(description, count=task_count)
            result.format_step = StepResult(
                ok=True,
                message=f"AI formatted {len(result.tasks)} tasks",
                data={"tasks": result.tasks},
            )
        except Exception as e:
            result.format_step = StepResult(ok=False, message=str(e))
            return result
    else:
        try:
            result.tasks = read_tasks_from_file()
            result.format_step = StepResult(
                ok=True, message=f"Loaded {len(result.tasks)} tasks from task.md"
            )
        except Exception as e:
            result.format_step = StepResult(ok=False, message=str(e))
            return result

    if not result.tasks:
        result.format_step = StepResult(ok=False, message="No tasks resolved")
        return result

    # ── Step 2: Update Google Doc ────────────────────────────────────────────
    try:
        doc_meta = update_doc(result.tasks)
        result.doc_url = doc_meta["doc_url"]
        result.report_date = doc_meta["report_date"]
        result.day_num = doc_meta["day_num"]
        result.doc_step = StepResult(
            ok=True,
            message=f"Doc updated — {result.report_date}, Day {result.day_num}",
            data={"doc_url": result.doc_url},
        )
    except Exception as e:
        result.doc_step = StepResult(ok=False, message=str(e))
        return result

    # ── Step 3: Export PDF ───────────────────────────────────────────────────
    try:
        local_pdf = export_pdf(save_path=pdf_path)
        result.pdf_path = str(local_pdf)
        result.pdf_step = StepResult(
            ok=True,
            message=f"PDF saved: {local_pdf.name}",
            data={"pdf_path": str(local_pdf)},
        )
    except Exception as e:
        result.pdf_step = StepResult(ok=False, message=str(e))
        return result

    # ── Step 4: Save to summary.md (non-fatal) ───────────────────────────────
    try:
        append_tasks(result.tasks)
    except Exception:
        pass

    # ── Step 5: Upload + Send Chat (optional) ────────────────────────────────
    if send_chat:
        try:
            pdf_drive_link = upload_pdf(local_pdf)
            result.pdf_drive_link = pdf_drive_link
            message = build_message(
                result.tasks, result.doc_url, pdf_drive_link, result.day_num
            )
            send_to_chat(message)
            result.chat_step = StepResult(
                ok=True,
                message="Sent to Google Chat",
                data={"pdf_drive_link": pdf_drive_link},
            )
        except Exception as e:
            result.chat_step = StepResult(ok=False, message=str(e))
    else:
        result.chat_step = StepResult(ok=True, message="Skipped")

    return result

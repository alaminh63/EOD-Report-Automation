"""FastAPI web app — DDR Report Automation."""

import logging
import logging.config
import time
from pathlib import Path

import asyncio

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import config, pipeline as pipe
from ..ai_formatter import format_tasks
from ..llm_router import FREE_MODELS, get_model_chain

# ── Logging ──────────────────────────────────────────────────────────────────
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "ddr": {
            "format": "%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
            "datefmt": "%H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "ddr",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "src.ddr": {"level": "DEBUG"},
        "uvicorn.access": {"level": "WARNING"},   # suppress per-request noise
    },
})

logger = logging.getLogger("src.ddr.web")

# Runtime preferred model — overrides config without mutating module
_preferred_model: str = config.OPENROUTER_MODEL or (FREE_MODELS[0] if FREE_MODELS else "")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="DDR Report Automation")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ── Middleware: log every API call with timing ────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        t0 = time.monotonic()
        response = await call_next(request)
        ms = int((time.monotonic() - t0) * 1000)
        logger.info("%-6s %-22s %s  %dms",
                    request.method, request.url.path,
                    response.status_code, ms)
        return response
    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.post("/api/preview")
async def preview(
    description: str = Form(""),
    task_count: int = Form(5),
):
    """AI-format free text into tasks. Returns tasks + attempt log."""
    if not description.strip():
        return JSONResponse({"ok": False, "error": "description is empty"}, status_code=400)
    try:
        from ..llm_router import RouterResult, complete
        from ..ai_formatter import _build_prompt
        logger.info("AI format — %d tasks | desc: %.60s…", task_count, description.strip())
        result: RouterResult = await asyncio.to_thread(
            complete,
            _build_prompt(description.strip(), task_count),
            512,
            0.3,
        )
        for a in result.attempts:
            status = "✓ OK " if a.ok else "✗ FAIL"
            logger.info("  %s  %-45s  %dms%s",
                        status, a.model, a.latency_ms,
                        f"  [{a.error}]" if a.error else "")
        logger.info("  → used: %s", result.model_used)

        raw = result.text
        tasks = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(tasks) < task_count:
            tasks.extend(["(no task)"] * (task_count - len(tasks)))
        tasks = tasks[:task_count]
        attempts = [
            {"model": a.model, "ok": a.ok, "error": a.error, "ms": a.latency_ms}
            for a in result.attempts
        ]
        return {"ok": True, "tasks": tasks, "model_used": result.model_used, "attempts": attempts}
    except Exception as e:
        logger.error("AI format failed: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/run")
async def run_report(
    tasks: str = Form(...),
    send_chat: bool = Form(False),
):
    """Execute pipeline: update Doc → export PDF → optionally send Chat."""
    task_list = [t.strip() for t in tasks.splitlines() if t.strip()]
    if not task_list:
        return JSONResponse({"ok": False, "error": "No tasks provided"}, status_code=400)

    logger.info("Pipeline start — %d tasks  send_chat=%s", len(task_list), send_chat)
    for i, t in enumerate(task_list, 1):
        logger.info("  [%d] %s", i, t)

    result = await asyncio.to_thread(pipe.run, tasks=task_list, send_chat=send_chat)
    d = result.to_dict()

    for k, v in d.get("steps", {}).items():
        icon = "✓" if v.get("ok") else "✗"
        logger.info("  %s %-8s  %s", icon, k, v.get("message", ""))

    return d


@app.get("/api/models")
async def models():
    return {"models": get_model_chain(), "preferred": _preferred_model}


@app.post("/api/set-model")
async def set_model(model: str = Form(...)):
    global _preferred_model
    _preferred_model = model
    config.OPENROUTER_MODEL = model
    logger.info("Model switched → %s", model)
    chain = get_model_chain()
    return {"ok": True, "model": model, "chain": chain}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "doc_id": config.DOC_ID[:12] + "...",
        "chat_space": config.SPACE_NAME or "not set",
        "openrouter": "configured" if config.OPENROUTER_API_KEY else "missing key",
        "model_chain": get_model_chain(),
        "preferred": _preferred_model,
    }

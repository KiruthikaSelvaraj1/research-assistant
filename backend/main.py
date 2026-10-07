"""
main.py — FastAPI application entry point

Endpoints:
  GET  /health
  POST /upload          — accepts 1-3 PDF files, returns session_id
  POST /analyze         — triggers background crew run, returns job_id
  GET  /progress/{id}   — poll for live agent progress
  GET  /results/{id}    — return full structured results when complete
"""
from __future__ import annotations

import shutil
import sys
import threading
import uuid
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# CrewAI 1.15 annotates threading.Lock as a type. Python 3.11 exposes it as
# a factory function, so provide a callable type-compatible adapter at import time.
_thread_lock_factory = threading.Lock


class _CompatibleLock:
    def __new__(cls):
        return _thread_lock_factory()


threading.Lock = _CompatibleLock

from backend.crew import ResearchCrew
from backend.models import AnalyzeRequest, AnalyzeResponse, UploadResponse

load_dotenv()

# ---------------------------------------------------------------------------
# In-memory stores (no database needed for this scope)
# ---------------------------------------------------------------------------

sessions: dict = {}   # session_id → {"pdf_paths": [...], "filenames": [...]}
jobs: dict = {}       # job_id     → {"status", "progress", "results", "error"}

UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Research Assistant API",
    description="Multi-agent system for academic paper analysis (CrewAI + Claude).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create upload directory on startup
@app.on_event("startup")
async def startup() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "message": "AI Research Assistant API is running"}


@app.post("/upload", response_model=UploadResponse)
async def upload_papers(files: list[UploadFile] = File(...)) -> UploadResponse:
    """
    Accept 1-3 PDF files and persist them to a per-session directory.
    Returns a session_id that is required for the /analyze call.
    """
    if not files:
        raise HTTPException(400, "No files provided.")
    if len(files) > 3:
        raise HTTPException(400, "Maximum 3 papers allowed per analysis run.")

    for f in files:
        fname = f.filename or ""
        if not fname.lower().endswith(".pdf"):
            raise HTTPException(400, f"'{fname}' is not a PDF file.")

    session_id = str(uuid.uuid4())
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True)

    saved_paths: list[str] = []
    filenames: list[str] = []

    for f in files:
        # Sanitise filename
        raw_name = f.filename or f"paper_{len(saved_paths)+1}.pdf"
        safe_name = (
            "".join(c for c in raw_name if c.isalnum() or c in "._- ").strip()
            or f"paper_{len(saved_paths)+1}.pdf"
        )
        dest = session_dir / safe_name

        content = await f.read()
        if len(content) == 0:
            shutil.rmtree(session_dir, ignore_errors=True)
            raise HTTPException(400, f"'{raw_name}' is empty.")
        if len(content) > MAX_FILE_SIZE:
            shutil.rmtree(session_dir, ignore_errors=True)
            raise HTTPException(400, f"'{raw_name}' exceeds the 50 MB limit.")

        dest.write_bytes(content)
        saved_paths.append(str(dest))
        filenames.append(raw_name)

    sessions[session_id] = {"pdf_paths": saved_paths, "filenames": filenames}

    return UploadResponse(
        session_id=session_id,
        filenames=filenames,
        message=f"Successfully uploaded {len(files)} paper(s). Ready to analyse.",
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: AnalyzeRequest, background_tasks: BackgroundTasks
) -> AnalyzeResponse:
    """
    Trigger the multi-agent crew analysis for the given session.
    Returns a job_id immediately; the heavy work runs in a background thread.
    """
    if request.session_id not in sessions:
        raise HTTPException(
            404, "Session not found. Upload papers first via POST /upload."
        )

    pdf_paths = sessions[request.session_id]["pdf_paths"]
    if not pdf_paths:
        raise HTTPException(400, "No papers found in this session.")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "session_id": request.session_id,
        "progress": [
            {
                "step": 0,
                "agent": "System",
                "status": "queued",
                "message": f"Analysis queued for {len(pdf_paths)} paper(s).",
            }
        ],
        "results": None,
        "error": None,
    }

    background_tasks.add_task(_run_analysis, job_id, pdf_paths)

    return AnalyzeResponse(
        job_id=job_id,
        status="queued",
        message=f"Analysis started. Poll GET /progress/{job_id} for live updates.",
    )


def _run_analysis(job_id: str, pdf_paths: list[str]) -> None:
    """
    Synchronous function executed in FastAPI's background thread pool.
    Runs the full 5-agent CrewAI pipeline and stores results.
    """
    try:
        jobs[job_id]["status"] = "analyzing"
        crew = ResearchCrew(pdf_paths, job_id=job_id, jobs_store=jobs)
        results = crew.run()

        jobs[job_id]["status"] = "complete"
        jobs[job_id]["results"] = results
        jobs[job_id]["progress"].append(
            {
                "step": 6,
                "agent": "System",
                "status": "complete",
                "message": "All agents finished. Results are ready!",
            }
        )

    except Exception as exc:  # noqa: BLE001
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(exc)
        jobs[job_id]["progress"].append(
            {
                "step": -1,
                "agent": "System",
                "status": "error",
                "message": f"Analysis failed: {exc}",
            }
        )


@app.get("/progress/{job_id}")
async def get_progress(job_id: str) -> dict:
    """Poll for the current status and progress events of a job."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found.")
    j = jobs[job_id]
    return {
        "job_id": job_id,
        "status": j["status"],
        "progress": j["progress"],
        "has_results": j["results"] is not None,
        "error": j["error"],
    }


@app.get("/results/{job_id}")
async def get_results(job_id: str) -> JSONResponse:
    """Return the full structured analysis results once the job is complete."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found.")

    j = jobs[job_id]

    if j["status"] == "error":
        raise HTTPException(500, f"Analysis failed: {j['error']}")

    if j["status"] in ("queued", "analyzing"):
        raise HTTPException(
            202,
            detail="Analysis still in progress. Poll GET /progress/{job_id} and retry later.",
        )

    if j["results"] is None:
        raise HTTPException(404, "Results not available.")

    return JSONResponse(content=j["results"])

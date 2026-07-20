"""
In-memory job and session store.
No database required — state lives for the lifetime of the process.
"""
import uuid
import threading
from datetime import datetime
from typing import Optional

# Thread-safe dict access
_lock = threading.Lock()

# session_id -> {files: [{file_id, filename, path}]}
sessions: dict[str, dict] = {}

# job_id -> full job record
jobs: dict[str, dict] = {}


def create_session() -> str:
    session_id = str(uuid.uuid4())
    with _lock:
        sessions[session_id] = {"files": [], "created_at": datetime.utcnow().isoformat()}
    return session_id


def add_files_to_session(session_id: str, files: list[dict]) -> None:
    with _lock:
        if session_id not in sessions:
            sessions[session_id] = {"files": [], "created_at": datetime.utcnow().isoformat()}
        sessions[session_id]["files"].extend(files)


def get_session(session_id: str) -> Optional[dict]:
    return sessions.get(session_id)


def create_job(session_id: str) -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        jobs[job_id] = {
            "job_id": job_id,
            "session_id": session_id,
            "status": "queued",
            "progress": {
                "ingestion": "pending",
                "summarizer": "pending",
                "findings": "pending",
                "litreview": "pending",
                "future": "pending",
            },
            "results": None,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    return jobs.get(job_id)


def update_job_status(job_id: str, status: str) -> None:
    with _lock:
        if job_id in jobs:
            jobs[job_id]["status"] = status
            if status in ("completed", "failed"):
                jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()


def update_job_progress(job_id: str, agent: str, state: str) -> None:
    """state: 'pending' | 'running' | 'done' | 'error'"""
    with _lock:
        if job_id in jobs:
            jobs[job_id]["progress"][agent] = state


def set_job_results(job_id: str, results: dict) -> None:
    with _lock:
        if job_id in jobs:
            jobs[job_id]["results"] = results
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()


def set_job_error(job_id: str, error: str) -> None:
    with _lock:
        if job_id in jobs:
            jobs[job_id]["error"] = error
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()

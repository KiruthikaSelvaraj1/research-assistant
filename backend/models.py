"""Pydantic models for request/response types throughout the API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Upload / Session
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    session_id: str
    filenames: List[str]
    message: str


# ---------------------------------------------------------------------------
# Analyze / Job
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    session_id: str


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Concept Map
# ---------------------------------------------------------------------------

class ConceptMapNode(BaseModel):
    id: str
    label: str
    type: str = "concept"          # "paper" | "concept" | "theme"
    description: Optional[str] = ""


class ConceptMapEdge(BaseModel):
    source: str
    target: str
    relationship: str              # builds_on | contradicts | shares_method | shares_theme


class ConceptMap(BaseModel):
    nodes: List[ConceptMapNode] = Field(default_factory=list)
    edges: List[ConceptMapEdge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-Paper Results
# ---------------------------------------------------------------------------

class KeyFinding(BaseModel):
    finding_id: str = ""
    claim: str = ""
    methodology: str = ""
    results: str = ""
    limitations: str = ""
    significance: str = ""


class PaperResult(BaseModel):
    paper_index: int
    filename: str
    summary: str = ""
    findings: List[KeyFinding] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Full Analysis Results
# ---------------------------------------------------------------------------

class AnalysisResults(BaseModel):
    papers: List[PaperResult]
    lit_review: str = ""
    concept_map: ConceptMap = Field(default_factory=ConceptMap)
    future_directions: str = ""


# ---------------------------------------------------------------------------
# Job Status (for polling)
# ---------------------------------------------------------------------------

class ProgressEvent(BaseModel):
    step: int
    agent: str
    status: str   # "queued" | "running" | "complete" | "error"
    message: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: List[ProgressEvent] = Field(default_factory=list)
    has_results: bool = False
    error: Optional[str] = None

"""Pydantic models for request/response types throughout the API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


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


class PaperSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)


class DiscoveredPaper(BaseModel):
    paper_id: str
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    arxiv_url: Optional[str] = None
    source: str
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: str = ""
    abstract: str = ""
    type: str = "research output"
    doi_url: Optional[str] = None
    publisher_url: str
    pdf_url: Optional[str] = None
    license_url: Optional[str] = None
    full_text_available: bool = False


class PaperSearchResponse(BaseModel):
    papers: List[DiscoveredPaper] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class AnalyzeDiscoveredRequest(BaseModel):
    arxiv_ids: List[str] = Field(min_length=1, max_length=3)


class ConversationTurn(BaseModel):
    question: str = Field(max_length=1_000)
    answer: str = Field(max_length=2_500)


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1_000)
    history: List[ConversationTurn] = Field(default_factory=list, max_length=4)


class EvidenceCitation(BaseModel):
    paper_index: int
    filename: str
    page: int
    quote: str


class AskQuestionResponse(BaseModel):
    answer: str
    citations: List[EvidenceCitation] = Field(default_factory=list)
    abstained: bool = False


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

class FindingEvidence(BaseModel):
    page: int
    quote: str


class KeyFinding(BaseModel):
    finding_id: str = ""
    claim: str = ""
    methodology: str = ""
    results: str = ""
    limitations: str = ""
    significance: str = ""
    evidence: List[FindingEvidence] = Field(default_factory=list)


class PaperFindingOutput(BaseModel):
    finding_id: str
    claim: str
    methodology: str
    results: str
    limitations: str
    significance: str
    evidence: List[FindingEvidence] = Field(default_factory=list, max_length=1)

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_single_evidence(cls, value: Any) -> Any:
        return [value] if isinstance(value, dict) else value


class PaperAnalysisOutput(BaseModel):
    summary: str = Field(description="An evidence-grounded summary of 150 to 200 words.")
    findings: List[PaperFindingOutput] = Field(min_length=3, max_length=3)


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

"""
Agent 1 — Document Ingestion Specialist
Extracts and structures raw text from each uploaded PDF using the
custom PDFExtractionTool. Outputs cleaned text + detected sections.
"""
from crewai import Agent, LLM

from backend.tools.pdf_tool import PDFExtractionTool


def create_ingestion_agent(llm: LLM) -> Agent:
    return Agent(
        role="Document Ingestion Specialist",
        goal=(
            "Extract, clean, and structure raw text from academic PDF papers, "
            "accurately identifying document sections and metadata so every "
            "downstream analysis agent receives well-organised, reliable content."
        ),
        backstory=(
            "You are an expert in scientific document processing with a decade of experience "
            "parsing academic papers from every discipline. You have a talent for dealing with "
            "PDF formatting quirks — multi-column layouts, ligatures, inconsistent section headers "
            "— and for producing clean, structured output even from imperfect source files. "
            "The entire research pipeline depends on the quality of your extraction: if you miss "
            "a section, the downstream agents lose critical evidence. You take that responsibility "
            "seriously, always cross-checking the detected sections against the raw text and noting "
            "any extraction issues that downstream agents should be aware of."
        ),
        tools=[PDFExtractionTool()],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

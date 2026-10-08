"""
Custom CrewAI Tool: PDF Extraction

Wraps pdfplumber (with pypdf fallback) to extract text from academic PDFs
and detect common section headers (Abstract, Methods, Results, Conclusion).
"""
from __future__ import annotations

import json
import os
import re
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

MAX_SOURCE_CHARS = 250_000


class PDFExtractionInput(BaseModel):
    pdf_path: str = Field(
        ...,
        description="Absolute filesystem path to the PDF file to extract text from.",
    )


class PDFExtractionTool(BaseTool):
    name: str = "extract_pdf_text"
    description: str = (
        "Extracts text and structure from an academic PDF file. "
        "Detects common sections: Abstract, Introduction, Related Work, "
        "Methods, Results, Discussion, Conclusion. "
        "INPUT: absolute path to the PDF file. "
        "OUTPUT: JSON string with keys 'filename', 'full_text', 'sections', 'metadata'."
    )
    args_schema: Type[BaseModel] = PDFExtractionInput

    # ------------------------------------------------------------------
    # Public interface (BaseTool calls _run)
    # ------------------------------------------------------------------

    def extract_paper(self, pdf_path: str) -> dict:
        """Extract bounded text and section metadata without an LLM tool call."""
        source_pages, source_truncated = self._extract_pages(pdf_path)
        text = "\n\n".join(page["text"] for page in source_pages)
        if not text.strip():
            raise ValueError(
                f"No text could be extracted from {os.path.basename(pdf_path)} "
                "(the PDF may be scanned or image-only)."
            )

        sections = self._detect_sections(text)
        return {
            "filename": os.path.basename(pdf_path),
            # Bound source text passed into the analysis pipeline.
            "full_text": text[:5_000],
            "source_pages": source_pages,
            "source_truncated": source_truncated,
            "sections": sections,
            "metadata": {
                "char_count": len(text),
                "word_count": len(text.split()),
                "sections_detected": list(sections.keys()),
            },
        }

    def _run(self, pdf_path: str) -> str:  # noqa: D401
        try:
            return json.dumps(self.extract_paper(pdf_path), ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({
                "error": str(exc),
                "filename": os.path.basename(pdf_path) if pdf_path else "unknown",
                "full_text": "",
                "sections": {},
                "metadata": {},
            })

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_pages(self, pdf_path: str) -> tuple[list[dict], bool]:
        """Extract page text and retain PDF page numbers for verifiable citations."""
        try:
            import pdfplumber  # noqa: PLC0415

            with pdfplumber.open(pdf_path) as pdf:
                pages: list[dict] = []
                remaining = MAX_SOURCE_CHARS
                truncated = False
                for page_number, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text()
                    if not page_text:
                        continue
                    if remaining <= 0:
                        truncated = True
                        break
                    stored_text = page_text[:remaining]
                    pages.append({"page": page_number, "text": stored_text})
                    remaining -= len(stored_text)
                    if len(stored_text) < len(page_text):
                        truncated = True
                        break
                return pages, truncated
        except Exception:  # noqa: BLE001
            try:
                from pypdf import PdfReader  # noqa: PLC0415

                reader = PdfReader(pdf_path)
                pages: list[dict] = []
                remaining = MAX_SOURCE_CHARS
                truncated = False
                for page_number, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text()
                    if not page_text:
                        continue
                    if remaining <= 0:
                        truncated = True
                        break
                    stored_text = page_text[:remaining]
                    pages.append({"page": page_number, "text": stored_text})
                    remaining -= len(stored_text)
                    if len(stored_text) < len(page_text):
                        truncated = True
                        break
                return pages, truncated
            except Exception as exc2:  # noqa: BLE001
                raise RuntimeError(f"Both pdfplumber and pypdf failed: {exc2}") from exc2

    def _detect_sections(self, text: str) -> dict[str, str]:
        """
        Detect common academic sections using regex anchored at line starts.
        Returns a dict mapping section name → first 3 000 chars of content.
        """
        # Patterns: section header → content until next numbered section or known header
        _NEXT = r"(?=\n\s*(?:\d{1,2}\s*\.|\Z|abstract|introduction|related|background|method|experiment|result|discussion|conclusion|reference|acknowledg))"
        patterns: dict[str, str] = {
            "abstract": (
                r"(?:^|\n)\s*abstract\s*\n(.*?)" + _NEXT
            ),
            "introduction": (
                r"(?:^|\n)\s*(?:\d\s*\.?\s*)?introduction\s*\n(.*?)" + _NEXT
            ),
            "related_work": (
                r"(?:^|\n)\s*(?:\d\s*\.?\s*)?(?:related work|literature review|background)\s*\n(.*?)" + _NEXT
            ),
            "methods": (
                r"(?:^|\n)\s*(?:\d\s*\.?\s*)?(?:method(?:ology|s)?|approach|experimental setup)\s*\n(.*?)" + _NEXT
            ),
            "results": (
                r"(?:^|\n)\s*(?:\d\s*\.?\s*)?(?:results?|findings|experiments?|evaluation)\s*\n(.*?)" + _NEXT
            ),
            "discussion": (
                r"(?:^|\n)\s*(?:\d\s*\.?\s*)?discussion\s*\n(.*?)" + _NEXT
            ),
            "conclusion": (
                r"(?:^|\n)\s*(?:\d\s*\.?\s*)?conclusions?\s*\n(.*?)" + _NEXT
            ),
        }

        sections: dict[str, str] = {}
        for name, pat in patterns.items():
            m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if m:
                content = m.group(1).strip()
                if len(content) > 80:          # must be substantial
                    sections[name] = content[:800]

        if not sections:
            # Graceful fallback: take the first 1 500 chars as a preview
            sections["content_preview"] = text[:1_500]

        return sections

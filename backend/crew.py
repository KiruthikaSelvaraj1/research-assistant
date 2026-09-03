"""
crew.py — ResearchCrew

Assembles the 5 CrewAI agents into a sequential crew and orchestrates their
tasks dynamically based on the number of uploaded papers (1-3).

Task ordering per paper:
  Ingest → Summarise → Extract Findings
Then, once all papers are processed:
  Synthesise (cross-paper) → Future Directions

After kickoff, outputs are parsed and returned as a structured dict.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from crewai import Agent, Crew, LLM, Process, Task
from dotenv import load_dotenv

from backend.agents.findings_agent import create_findings_agent
from backend.agents.future_agent import create_future_agent
from backend.agents.ingestion_agent import create_ingestion_agent
from backend.agents.summarizer_agent import create_summarizer_agent
from backend.agents.synthesis_agent import create_synthesis_agent

load_dotenv()

# ---------------------------------------------------------------------------
# Patch CrewAI's cache_breakpoint marker to a no-op
#
# CrewAI 1.15+ unconditionally adds {"cache_breakpoint": True} to system
# messages for Anthropic prompt caching (crewai.llms.cache.mark_cache_breakpoint).
# When using non-Anthropic providers (Groq, Gemini, Ollama), litellm does NOT
# strip this key and the provider rejects it as an unsupported field.
#
# Fix: neuter the marker at the source so it never reaches litellm.
# ---------------------------------------------------------------------------
try:
    import crewai.llms.cache as _crew_cache
except ModuleNotFoundError:
    _crew_cache = None

if _crew_cache is not None:
    def _noop_mark(message: dict) -> dict:
        return message

    def _noop_strip(message: dict) -> None:
        pass

    _crew_cache.mark_cache_breakpoint = _noop_mark
    _crew_cache.strip_cache_breakpoint = _noop_strip
    print("[PATCH] crewai: cache_breakpoint marker neutered for non-Anthropic providers")

# ---------------------------------------------------------------------------
# LLM factory — supports multiple FREE and paid providers
# Priority: Gemini → Groq → Ollama (local) → Anthropic (paid)
# Set the matching API key in your .env file to activate a provider.
# Gemini has by far the best free tier (1M TPM vs Groq's 12k).
# ---------------------------------------------------------------------------

def get_llm() -> LLM:
    # ── 1. Google Gemini (FREE) ── 1 000 000 TPM, best free tier ────────────
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        model = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")
        print(f"[LLM] Using Google Gemini (FREE): {model}")
        return LLM(model=model, api_key=gemini_key, temperature=0.3, max_tokens=4096, num_retries=8)

    # ── 2. Groq (FREE) ── 12k TPM (70B) / 6k TPM (8B), rate-limit prone ────
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        # Keep the default on a model currently available to this provider.
        model = os.getenv("LLM_MODEL", "groq/qwen/qwen3.8-27b")
        print(f"[LLM] Using Groq (FREE): {model}")
        return LLM(model=model, api_key=groq_key, temperature=0.3, max_tokens=400, num_retries=24)

    # ── 3. Ollama (LOCAL — completely free, no internet needed) ─────────────
    ollama_model = os.getenv("OLLAMA_MODEL")
    if ollama_model:
        model = f"ollama/{ollama_model}"
        print(f"[LLM] Using Ollama (LOCAL/FREE): {model}")
        return LLM(model=model, temperature=0.3, max_tokens=2048)

    # ── 4. Anthropic Claude (PAID) ──────────────────────────────────────────
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        model = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6")
        print(f"[LLM] Using Anthropic (PAID): {model}")
        return LLM(model=model, api_key=anthropic_key, temperature=0.3, max_tokens=4096, num_retries=3)

    # ── No provider configured ───────────────────────────────────────────────
    raise ValueError(
        "\n\n❌ No LLM provider configured!\n"
        "Add ONE of these to your .env file:\n"
        "  GROQ_API_KEY=...      (FREE — get at console.groq.com)\n"
        "  GEMINI_API_KEY=...    (FREE — get at aistudio.google.com)\n"
        "  OLLAMA_MODEL=llama3.2 (FREE local — install ollama.ai first)\n"
        "  ANTHROPIC_API_KEY=... (PAID  — get at console.anthropic.com)\n"
    )


# ---------------------------------------------------------------------------
# Output parsers
# ---------------------------------------------------------------------------

def _parse_findings(raw: str) -> list[dict]:
    """Extract a JSON array of findings from the agent's raw output."""
    # Prefer fenced JSON block
    m = re.search(r"```json\s*(.*?)```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: first JSON array in the text
    m2 = re.search(r"\[.*\]", raw, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(0))
        except json.JSONDecodeError:
            pass

    # Final fallback: wrap raw text
    return [
        {
            "finding_id": "F1",
            "claim": "Could not parse structured findings — see raw output.",
            "methodology": "",
            "results": raw[:500],
            "limitations": "",
            "significance": "",
        }
    ]


def _parse_synthesis(raw: str) -> tuple[str, dict]:
    """
    Split the synthesis agent's output into:
      - literature review prose
      - concept map dict (nodes + edges)
    """
    # Literature review: everything before the JSON block or ## CONCEPT MAP JSON header
    lit_review = ""
    lit_m = re.search(
        r"##\s*LITERATURE REVIEW\s*\n(.*?)(?=##\s*CONCEPT MAP JSON|\Z)",
        raw,
        re.DOTALL | re.IGNORECASE,
    )
    if lit_m:
        lit_review = lit_m.group(1).strip()
    else:
        # Fallback: everything before the first ``` block
        json_start = raw.find("```json")
        lit_review = raw[:json_start].strip() if json_start > 0 else raw.strip()

    # Concept map JSON
    concept_map: dict = {"nodes": [], "edges": []}
    json_m = re.search(r"```json\s*(.*?)```", raw, re.DOTALL)
    if json_m:
        try:
            parsed = json.loads(json_m.group(1))
            concept_map = {
                "nodes": parsed.get("nodes", []),
                "edges": parsed.get("edges", []),
            }
        except json.JSONDecodeError:
            pass

    return lit_review, concept_map


# ---------------------------------------------------------------------------
# Main crew class
# ---------------------------------------------------------------------------

class ResearchCrew:
    """
    Orchestrates the 5-agent research analysis pipeline.

    Args:
        pdf_paths:   List of absolute paths to uploaded PDFs (1-3).
        job_id:      Optional job ID used to update the shared jobs store.
        jobs_store:  Optional reference to the in-memory jobs dict in main.py.
    """

    def __init__(
        self,
        pdf_paths: list[str],
        job_id: Optional[str] = None,
        jobs_store: Optional[dict] = None,
    ) -> None:
        self.pdf_paths = pdf_paths
        self.job_id = job_id
        self.jobs_store = jobs_store
        self.llm = get_llm()

    # ------------------------------------------------------------------
    # Progress helper
    # ------------------------------------------------------------------

    def _progress(self, step: int, agent: str, status: str, message: str) -> None:
        if self.jobs_store and self.job_id:
            self.jobs_store[self.job_id]["progress"].append(
                {"step": step, "agent": agent, "status": status, "message": message}
            )

    # ------------------------------------------------------------------
    # Task builders
    # ------------------------------------------------------------------

    def _build_ingest_task(self, agent: Agent, paper_num: int, pdf_path: str) -> Task:
        filename = os.path.basename(pdf_path)
        return Task(
            description=(
                f"Use the extract_pdf_text tool to extract content from Paper {paper_num} "
                f"located at: {pdf_path}\n\n"
                f"After extraction, analyse the result and report:\n"
                f"1. The paper's title and authors (typically in the first few lines).\n"
                f"2. Which sections were successfully detected.\n"
                f"3. The research domain and main topic.\n"
                f"4. Any extraction issues (e.g. scanned pages, missing sections).\n\n"
                f"Return the FULL extraction result — include the complete section texts so "
                f"that downstream agents have everything they need."
            ),
            expected_output=(
                f"Complete extraction of Paper {paper_num} ({filename}) including detected "
                f"sections (abstract, methods, results, conclusion), paper title/authors "
                f"if detectable, and the full extracted text."
            ),
            agent=agent,
        )

    def _build_summary_task(
        self, agent: Agent, paper_num: int, ingest_task: Task
    ) -> Task:
        return Task(
            description=(
                f"Based on the extracted content of Paper {paper_num} (provided by the "
                f"Ingestion Agent in context), write a concise, accurate academic summary.\n\n"
                f"Requirements:\n"
                f"• Length: exactly 150-250 words — count carefully.\n"
                f"• First sentence: state the paper's core research question or objective.\n"
                f"• Cover: methodology used (data, approach, experimental setup).\n"
                f"• Cover: main findings and their magnitude — include specific numbers.\n"
                f"• Cover: key limitations acknowledged by the authors.\n"
                f"• Final sentence: broader contribution to the field.\n\n"
                f"Style: clear academic prose, no bullet points, no 'This paper ...' opener, "
                f"no hedging phrases like 'appears to' or 'seems to'."
            ),
            expected_output=(
                f"A 150-250 word academic summary of Paper {paper_num} covering: "
                f"research objective, methodology, key findings with specific metrics, "
                f"limitations, and broader significance."
            ),
            agent=agent,
            context=[ingest_task],
        )

    def _build_findings_task(
        self, agent: Agent, paper_num: int, ingest_task: Task
    ) -> Task:
        return Task(
            description=(
                f"Based on the extracted content of Paper {paper_num} (from the Ingestion "
                f"Agent in context), extract the key findings as a structured JSON list.\n\n"
                f"Return ONLY a JSON array — no prose before or after — in this exact schema:\n"
                f"```json\n"
                f"[\n"
                f"  {{\n"
                f'    "finding_id": "F{paper_num}_1",\n'
                f'    "claim": "One clear sentence stating the finding",\n'
                f'    "methodology": "How this was established (method, dataset, experiment)",\n'
                f'    "results": "Specific evidence with exact numbers/percentages",\n'
                f'    "limitations": "Limitations the authors acknowledge for this finding",\n'
                f'    "significance": "Why this finding matters to the field"\n'
                f"  }}\n"
                f"]\n"
                f"```\n\n"
                f"Rules:\n"
                f"• Include 3-6 findings per paper.\n"
                f"• finding_id format: F{paper_num}_1, F{paper_num}_2, …\n"
                f"• Use exact numbers from the paper, not paraphrases.\n"
                f"• Distinguish empirical findings from speculative claims."
            ),
            expected_output=(
                f"Valid JSON array with 3-6 structured findings from Paper {paper_num}, "
                f"each with finding_id, claim, methodology, results, limitations, significance."
            ),
            agent=agent,
            context=[ingest_task],
        )

    def _build_synthesis_task(
        self,
        agent: Agent,
        n: int,
        findings_tasks: list[Task],
        summary_tasks: list[Task],
    ) -> Task:
        paper_ids = ", ".join(f"paper_{i+1}" for i in range(n))
        return Task(
            description=(
                f"You have received key findings and summaries from {n} research paper(s) "
                f"as context. Synthesise these into a cohesive literature review and "
                f"concept map.\n\n"
                f"SYNTHESIS REQUIREMENTS (not a sequential list of papers):\n"
                f"1. Where do the papers AGREE or build on each other? (cite finding IDs: F1_1, etc.)\n"
                f"2. Where do papers CONTRADICT or challenge each other?\n"
                f"3. How do the METHODOLOGICAL APPROACHES differ?\n"
                f"4. What has been ESTABLISHED vs. what remains OPEN or uncertain?\n"
                f"5. What is the overall intellectual landscape these papers define?\n\n"
                f"OUTPUT — follow this EXACT structure:\n\n"
                f"## LITERATURE REVIEW\n"
                f"[400-600 words of synthesised analytical prose. Reference papers as "
                f"'Paper 1', 'Paper 2', etc. Be comparative and analytical, not descriptive.]\n\n"
                f"## CONCEPT MAP JSON\n"
                f"```json\n"
                f"{{\n"
                f'  "nodes": [\n'
                f'    {{"id": "paper_1", "label": "Short Paper 1 Title", "type": "paper", "description": "One-line description"}},\n'
                f'    {{"id": "concept_1", "label": "Key Theme", "type": "concept", "description": "What this represents"}},\n'
                f'    {{"id": "theme_1", "label": "Shared Method", "type": "theme", "description": "Description"}}\n'
                f"  ],\n"
                f'  "edges": [\n'
                f'    {{"source": "paper_1", "target": "concept_1", "relationship": "shares_theme"}},\n'
                f'    {{"source": "paper_1", "target": "paper_2", "relationship": "builds_on"}}\n'
                f"  ]\n"
                f"}}\n"
                f"```\n\n"
                f"Allowed relationship types: builds_on | contradicts | shares_method | shares_theme\n"
                f"Node count: {n + 3} to {n + 7} nodes (paper nodes: {paper_ids}, plus concept/theme nodes).\n"
                f"Edge count: {n + 2} to {n * 4 + 2} edges.\n"
                f"CRITICAL: Paper node IDs MUST be: {paper_ids}."
            ),
            expected_output=(
                f"A 400-600 word literature review synthesis (## LITERATURE REVIEW section) "
                f"followed by a valid JSON concept map (## CONCEPT MAP JSON section) with "
                f"nodes and edges encoding relationships between papers, concepts, and themes."
            ),
            agent=agent,
            context=findings_tasks + summary_tasks,
        )

    def _build_future_task(
        self,
        agent: Agent,
        n: int,
        synthesis_task: Task,
        findings_tasks: list[Task],
    ) -> Task:
        return Task(
            description=(
                f"Based on the literature review and key findings from {n} papers "
                f"(provided in context), identify 3-5 concrete future research directions.\n\n"
                f"For each direction, provide:\n"
                f"• A descriptive title\n"
                f"• One specific sentence stating the research direction\n"
                f"• Motivation citing specific papers/findings (Paper 1, F1_2, etc.)\n"
                f"• Brief methodological approach that could address it\n\n"
                f"Format each direction EXACTLY as:\n"
                f"1. **[Direction Title]**\n"
                f"   Research Direction: [Specific one-sentence statement]\n"
                f"   Motivation: [Evidence from Paper X, finding F_Y, or stated limitation]\n"
                f"   Approach: [Methodological suggestion]\n\n"
                f"Avoid vague directions like 'more research is needed.' Be specific and grounded."
            ),
            expected_output=(
                f"3-5 formatted future research directions, each with a bold title, "
                f"specific direction statement, motivation citing specific papers/findings, "
                f"and a methodological approach suggestion."
            ),
            agent=agent,
            context=[synthesis_task] + findings_tasks,
        )

    # ------------------------------------------------------------------
    # Main run method
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Build and execute the research crew. Returns a structured results dict."""
        n = len(self.pdf_paths)

        # Instantiate agents
        ingestion_agent = create_ingestion_agent(self.llm)
        summarizer_agent = create_summarizer_agent(self.llm)
        findings_agent = create_findings_agent(self.llm)
        synthesis_agent = create_synthesis_agent(self.llm)
        future_agent = create_future_agent(self.llm)

        # Build tasks interleaved per paper (ensures context is fresh for each paper)
        all_tasks: list[Task] = []
        ingest_tasks: list[Task] = []
        summary_tasks: list[Task] = []
        findings_tasks: list[Task] = []

        self._progress(1, "Ingestion Agent", "running", f"Extracting text from {n} paper(s)…")

        for i, pdf_path in enumerate(self.pdf_paths):
            paper_num = i + 1

            ingest = self._build_ingest_task(ingestion_agent, paper_num, pdf_path)
            summary = self._build_summary_task(summarizer_agent, paper_num, ingest)
            findings = self._build_findings_task(findings_agent, paper_num, ingest)

            all_tasks.extend([ingest, summary, findings])
            ingest_tasks.append(ingest)
            summary_tasks.append(summary)
            findings_tasks.append(findings)

        self._progress(2, "Summarizer Agent", "running", "Generating per-paper summaries…")
        self._progress(3, "Key Findings Agent", "running", "Extracting structured key findings…")

        synthesis = self._build_synthesis_task(
            synthesis_agent, n, findings_tasks, summary_tasks
        )
        all_tasks.append(synthesis)

        self._progress(4, "Synthesis Agent", "running", "Synthesising literature review and concept map…")

        future = self._build_future_task(future_agent, n, synthesis, findings_tasks)
        all_tasks.append(future)

        self._progress(5, "Future Directions Agent", "running", "Identifying research gaps…")

        # step_callback: minimal pause between steps for Gemini (60 RPM, 1M TPM
        # free tier) — no significant rate-limiting needed.
        _step_count = [0]
        def _pace_step(step_output):
            _step_count[0] += 1
            wait = 2  # seconds — Gemini free tier handles 60 RPM, just a small buffer
            print(f"[Rate-limit guard] Step {_step_count[0]} done. Waiting {wait}s before next step…")
            time.sleep(wait)

        # Assemble the crew
        crew = Crew(
            agents=[
                ingestion_agent,
                summarizer_agent,
                findings_agent,
                synthesis_agent,
                future_agent,
            ],
            tasks=all_tasks,
            process=Process.sequential,
            step_callback=_pace_step,
            verbose=True,
        )

        # Fire!
        crew.kickoff()

        # ------------------------------------------------------------------
        # Parse outputs
        # ------------------------------------------------------------------
        paper_results = []
        for i, (ingest_t, summary_t, findings_t) in enumerate(
            zip(ingest_tasks, summary_tasks, findings_tasks)
        ):
            summary_raw = (summary_t.output.raw if summary_t.output else "").strip()
            findings_raw = (findings_t.output.raw if findings_t.output else "[]").strip()

            paper_results.append(
                {
                    "paper_index": i + 1,
                    "filename": os.path.basename(self.pdf_paths[i]),
                    "summary": summary_raw,
                    "findings": _parse_findings(findings_raw),
                }
            )

        synthesis_raw = (synthesis.output.raw if synthesis.output else "").strip()
        lit_review, concept_map = _parse_synthesis(synthesis_raw)

        future_raw = (future.output.raw if future.output else "").strip()

        return {
            "papers": paper_results,
            "lit_review": lit_review,
            "concept_map": concept_map,
            "future_directions": future_raw,
        }

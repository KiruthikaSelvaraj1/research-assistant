"""
crew.py — ResearchCrew

Extracts PDF text locally, then runs one analysis task per paper followed by
comparative synthesis and future directions.

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

from backend.agents.future_agent import create_future_agent
from backend.agents.summarizer_agent import create_summarizer_agent
from backend.agents.synthesis_agent import create_synthesis_agent
from backend.tools.pdf_tool import PDFExtractionTool

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
# Gemini's free tier has substantially more throughput than Groq's rate-limited tier.
# ---------------------------------------------------------------------------

def get_llm() -> LLM:
    requested_model = os.getenv("LLM_MODEL", "")
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if requested_model.startswith("ollama/"):
        print(f"[LLM] Using Ollama (LOCAL/FREE): {requested_model}")
        return LLM(model=requested_model, temperature=0.3, max_tokens=1536)

    # Respect an explicit Groq model choice; otherwise prefer Gemini when both
    # credentials are present to avoid Groq's comparatively tight output quota.
    use_groq_first = requested_model.startswith("groq/")
    providers = (
        ("groq", groq_key, "groq/qwen/qwen3.8-27b"),
        ("gemini", gemini_key, "gemini/gemini-3.8-flash"),
    )
    if not use_groq_first:
        providers = tuple(reversed(providers))

    for provider, api_key, default_model in providers:
        if not api_key:
            continue
        model = requested_model if requested_model.startswith(f"{provider}/") else default_model
        if provider == "groq":
            print(f"[LLM] Using Groq (FREE; rate limits may apply): {model}")
            return LLM(model=model, api_key=api_key, temperature=0.3, max_tokens=900, num_retries=24)
        print(f"[LLM] Using Google Gemini (FREE): {model}")
        return LLM(model=model, api_key=api_key, temperature=0.3, max_tokens=4096, num_retries=8)

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

def _parse_paper_analysis(raw: str, paper_num: int) -> tuple[str, list[dict]]:
    """Parse the combined summary/findings response and reject malformed output."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    candidates = [fenced.group(1).strip()] if fenced else [raw.strip()]
    if not fenced:
        object_start = raw.find("{")
        object_end = raw.rfind("}")
        if object_start >= 0 and object_end > object_start:
            candidates.append(raw[object_start:object_end + 1])

    parsed = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue

    if not isinstance(parsed, dict):
        raise ValueError(
            f"Could not parse Paper {paper_num} analysis as JSON. "
            "Please retry the analysis."
        )

    summary = parsed.get("summary")
    findings = parsed.get("findings")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"Paper {paper_num} analysis did not include a summary.")
    if not isinstance(findings, list) or not findings:
        raise ValueError(f"Paper {paper_num} analysis did not include key findings.")

    required_fields = {
        "finding_id", "claim", "methodology", "results", "limitations", "significance"
    }
    if any(
        not isinstance(finding, dict) or not required_fields.issubset(finding)
        for finding in findings
    ):
        raise ValueError(
            f"Paper {paper_num} findings are missing required fields. "
            "Please retry the analysis."
        )

    return summary.strip(), findings


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

    def _build_paper_analysis_task(
        self, agent: Agent, paper_num: int, paper_data: dict
    ) -> Task:
        return Task(
            description=(
                f"Analyze Paper {paper_num} using only the extracted source below. "
                f"Return one JSON object with exactly two top-level keys: `summary` and "
                f"`findings`. The summary must be 150-200 words and cover objective, "
                f"method/data, main results with exact reported numbers, limitations, "
                f"and contribution. `findings` must contain exactly the 3 most important "
                f"distinct findings. Each finding must contain `finding_id` (F{paper_num}_1 "
                f"through F{paper_num}_3), `claim`, `methodology`, `results`, `limitations`, "
                f"and `significance`. Keep each field concise but specific. Do not invent "
                f"numbers or limitations; write 'not reported in the supplied text' when "
                f"evidence is unavailable. Return valid JSON only, without markdown.\n\n"
                f"Source extraction:\n{json.dumps(paper_data, ensure_ascii=False)}"
            ),
            expected_output=(
                "Valid JSON with a 150-200 word summary and exactly three evidence-grounded "
                "key findings, each with the required structured fields."
            ),
            agent=agent,
        )

    def _build_synthesis_task(
        self,
        agent: Agent,
        n: int,
        paper_analysis_tasks: list[Task],
    ) -> Task:
        paper_ids = ", ".join(f"paper_{i+1}" for i in range(n))
        return Task(
            description=(
                f"You have received key findings and summaries from {n} research paper(s) "
                f"as context. Write an evidence-led comparative analysis, not a sequence "
                f"of paper summaries. Use only claims supported by the provided context; "
                f"never invent results, comparisons, or citations.\n\n"
                f"For {n} paper(s), write 300-450 words in total under these exact headings:\n"
                f"## LITERATURE REVIEW\n"
                f"### Shared findings and points of agreement\n"
                f"Compare the specific claims that align. For 2+ papers, cite at least "
                f"two direct comparisons using Paper N and finding IDs (for example F1_1). "
                f"For one paper, state that cross-paper comparison is not possible and "
                f"compare distinct results or claims within that paper instead.\n"
                f"### Differences, conflicts, and methods\n"
                f"Compare research questions, data, methods, and reported results. Explain "
                f"whether any apparent conflict is real or whether study design/context "
                f"could explain it. Say explicitly when the supplied evidence shows no "
                f"direct contradiction; do not manufacture one.\n"
                f"### Evidence strength and limitations\n"
                f"Compare what the evidence supports, what remains uncertain, and the "
                f"limitations that constrain conclusions. Cite the relevant paper/finding.\n"
                f"### Synthesis and open research gap\n"
                f"State the combined conclusion and one specific unresolved gap grounded "
                f"in the papers. Make clear when a conclusion is tentative.\n\n"
                f"Be analytical and specific; avoid generic filler and unsupported claims.\n\n"
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
                f"Include all {n} paper nodes plus 3-5 meaningful concept/theme nodes and "
                f"only evidence-supported edges. Paper nodes: {paper_ids}.\n"
                f"CRITICAL: Paper node IDs MUST be: {paper_ids}."
            ),
            expected_output=(
                f"A 300-450 word comparative literature review with all four requested "
                f"subheadings, followed by valid concept-map JSON with evidence-supported "
                f"paper/concept nodes and relationships."
            ),
            agent=agent,
            context=paper_analysis_tasks,
        )

    def _build_future_task(
        self,
        agent: Agent,
        n: int,
        synthesis_task: Task,
        paper_analysis_tasks: list[Task],
    ) -> Task:
        return Task(
            description=(
                f"Based only on the supplied literature review and findings from {n} "
                f"paper(s), propose exactly 3 distinct, feasible future research directions. "
                f"Each must address a real gap or limitation in the evidence, not merely "
                f"repeat a paper's conclusion. Do not invent citations, datasets, or results. "
                f"Use Paper N and finding IDs (such as F1_2) when available. Clearly mark "
                f"proposed hypotheses as hypotheses, not established facts.\n\n"
                f"Write 80-120 words per direction and use this exact format:\n"
                f"1. **[Direction Title]**\n"
                f"   Research Question: [Specific, answerable question or hypothesis.]\n"
                f"   Evidence Gap: [What is unknown and why; cite Paper N/Finding ID and "
                f"the relevant result or limitation.]\n"
                f"   Proposed Study: [Concrete design, population/data, comparison or "
                f"intervention, and key method.]\n"
                f"   Evaluation & Expected Contribution: [Primary outcomes/metrics, what "
                f"result would support the hypothesis, and how the study would advance "
                f"understanding.]\n\n"
                f"Make the three directions non-overlapping and specific enough that a "
                f"researcher could begin designing each study. Do not output an introduction "
                f"or a generic concluding paragraph."
            ),
            expected_output=(
                f"Exactly three evidence-grounded research proposals, each with a title, "
                f"research question, cited evidence gap, concrete study design, and "
                f"evaluation plan with expected contribution."
            ),
            agent=agent,
            context=[synthesis_task] + paper_analysis_tasks,
        )

    # ------------------------------------------------------------------
    # Main run method
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Build and execute the research crew. Returns a structured results dict."""
        n = len(self.pdf_paths)

        # PDF text extraction is deterministic local work, not an LLM task.
        # Summaries and findings are produced together in one model call per paper.
        paper_analyst = create_summarizer_agent(self.llm)
        synthesis_agent = create_synthesis_agent(self.llm)
        future_agent = create_future_agent(self.llm)

        # Build one model task per paper, followed by the two cross-paper tasks.
        all_tasks: list[Task] = []
        paper_analysis_tasks: list[Task] = []

        self._progress(1, "PDF Extraction", "running", f"Extracting text from {n} paper(s)…")
        pdf_tool = PDFExtractionTool()

        for i, pdf_path in enumerate(self.pdf_paths):
            paper_num = i + 1
            paper_data = pdf_tool.extract_paper(pdf_path)
            paper_data["full_text"] = paper_data["full_text"][:3_000]
            paper_data["sections"] = {
                name: section[:400]
                for name, section in paper_data["sections"].items()
            }
            paper_task = self._build_paper_analysis_task(
                paper_analyst, paper_num, paper_data
            )
            all_tasks.append(paper_task)
            paper_analysis_tasks.append(paper_task)

        self._progress(1, "PDF Extraction", "complete", f"Extracted text from {n} paper(s).")
        self._progress(2, "Paper Analysis", "running", "Generating summaries and key findings…")

        synthesis = self._build_synthesis_task(
            synthesis_agent, n, paper_analysis_tasks
        )
        all_tasks.append(synthesis)

        future = self._build_future_task(
            future_agent, n, synthesis, paper_analysis_tasks
        )
        all_tasks.append(future)

        # Only add a small buffer for cloud providers; local Ollama needs no
        # inter-step rate-limit delay.
        _step_count = [0]
        def _pace_step(step_output):
            _step_count[0] += 1
            wait = 0 if self.llm.model.startswith("ollama/") else 2
            if wait:
                print(f"[Rate-limit guard] Step {_step_count[0]} done. Waiting {wait}s before next step…")
                time.sleep(wait)

        completed_tasks = [0]

        def _report_task_progress(_task_output):
            completed_tasks[0] += 1
            if completed_tasks[0] == n:
                self._progress(2, "Paper Analysis", "complete", "All papers summarized and key findings extracted.")
                self._progress(3, "Comparative Synthesis", "running", "Comparing evidence and mapping concepts…")
            elif completed_tasks[0] == n + 1:
                self._progress(3, "Comparative Synthesis", "complete", "Comparative literature review and concept map ready.")
                self._progress(4, "Future Directions", "running", "Building evidence-grounded research proposals…")
            elif completed_tasks[0] == n + 2:
                self._progress(4, "Future Directions", "complete", "Future research proposals ready.")

        # Assemble the crew
        crew = Crew(
            agents=[
                paper_analyst,
                synthesis_agent,
                future_agent,
            ],
            tasks=all_tasks,
            process=Process.sequential,
            step_callback=_pace_step,
            task_callback=_report_task_progress,
            verbose=False,
        )

        # Fire!
        crew.kickoff()

        # ------------------------------------------------------------------
        # Parse outputs
        # ------------------------------------------------------------------
        paper_results = []
        for i, paper_task in enumerate(paper_analysis_tasks):
            raw = paper_task.output.raw if paper_task.output else ""
            summary, findings = _parse_paper_analysis(raw, i + 1)

            paper_results.append(
                {
                    "paper_index": i + 1,
                    "filename": os.path.basename(self.pdf_paths[i]),
                    "summary": summary,
                    "findings": findings,
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

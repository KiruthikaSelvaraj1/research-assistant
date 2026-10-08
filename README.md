# AI Research Assistant 🧠

A research-focused assistant for discovering and comparing 1-3 academic papers. It
combines structured AI analysis with checkable PDF evidence; it does not claim to
replace expert review or guarantee that model-generated interpretations are correct.

**Live app:** [ai-research-assistant-as88.onrender.com](https://ai-research-assistant-as88.onrender.com/)

It produces:

- **Per-paper summaries** — 150-200 word precision summaries
- **Structured key findings** — claims, methodology, metrics, and limitations as JSON  
- **Verifiable evidence links** — source quotations linked to the paper and PDF page
- **Side-by-side evidence matrix** — compare structured claims, methods, results, and limitations
- **Downloadable reports** — export complete analyses as Markdown or structured JSON
- **Synthesised literature review** — cross-paper analysis (not sequential summaries)  
- **Interactive concept map** — force-directed D3 graph of papers, concepts, and relationships  
- **Future research directions** — three grounded study proposals with paper citations
- **Cross-paper Q&A** — questions answered from retrieved passages with verified quotations
- **Topic-based paper discovery** — search Crossref and arXiv, select open arXiv papers, and send them directly to analysis

---

## Architecture

```mermaid
graph TD
    UI["React SPA (Vite + D3)"]
    API["FastAPI Backend"]
    CROSSREF["Crossref public works API"]
    ARXIV["arXiv search and PDF API"]
    CREW["CrewAI Sequential Pipeline"]
    LLM["Configured LLM provider (Gemini, Groq, Ollama, or Anthropic)"]

    UI -->|POST /upload| API
    UI -->|POST /search| API
    UI -->|POST /analyze-discovered| API
    UI -->|POST /analyze| API
    UI -->|GET /progress| API
    UI -->|GET /results| API
    UI -->|POST /ask/{job_id}| API

    API -->|BackgroundTask| CREW
    API -->|Search scholarly metadata| CROSSREF
    API -->|Search / fetch selected PDFs| ARXIV
    CREW --> A1["📥 Local page-aware PDF extraction\n(no LLM call)"]
    CREW --> A2["✍️ Per-paper analysis\n(summary + findings + evidence in one call)"]
    CREW --> A3["📚 Comparative synthesis\n(lit review + concept map)"]
    CREW --> A4["🚀 Future directions"]

    A2 & A3 & A4 --> LLM
    A1 --> QA["Local passage retrieval"]
    QA -->|Verified passages| LLM

    style A3 fill:#6366f1,color:#fff
```

### Agent Roles

| Agent | Role | Output |
|---|---|---|
| **PDF extraction** | Extracts page-aware text and detects sections locally | Source text + section metadata |
| **Paper analysis** | Summarizes and extracts findings in one LLM call per paper | Summary + structured findings with page-linked quotations |
| **Comparative synthesis** | Compares findings and methods across papers | Literature review + concept map JSON |
| **Future directions** | Proposes research questions and study designs grounded in evidence | Three structured proposals |

Task flow (for 2 papers):
```
Extract PDFs locally
       ↓
Paper analysis 1 → Paper analysis 2
       ↓
Comparative synthesis → Future directions
```

The pipeline makes `number of papers + 2` LLM calls rather than separate
ingestion, summary, and findings calls for every paper. PDF extraction is local.
The evidence matrix is rendered from the structured findings and does not require
another model call.

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- An API key for Google Gemini, Groq, or Anthropic (or a local Ollama installation)

### 1. Clone and configure environment

```bash
git clone https://github.com/KiruthikaSelvaraj1/research-assistant.git
cd research-assistant
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Run the backend

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001
```

### 5. Run the frontend (separate terminal)

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

Gemini is preferred when both Gemini and Groq keys are configured because free Groq
quotas can limit output tokens per minute. To explicitly use Groq, set
`LLM_MODEL=groq/qwen/qwen3.8-27b`; if its quota is exhausted, wait for the provider's
reset window or use a provider with a higher available quota. Gemini defaults to
`gemini/gemini-3.8-flash`; set `LLM_MODEL=gemini/<model-id>` to choose another
Gemini API model. To use a locally running Ollama model instead, set
`LLM_MODEL=ollama/<model-name>` (for example, `ollama/llama3.2:3b`) and ensure
Ollama is installed and the model has been downloaded with `ollama pull`.

### Deploy to Render

The repository includes a Render Blueprint (`render.yaml`) and a multi-stage
`Dockerfile`. In Render, choose **New → Blueprint**, connect this GitHub repository,
and deploy the `init` branch. The single web service builds the React frontend and
serves it from FastAPI.

Before running analysis, add `GEMINI_API_KEY` in the Render service's Environment
settings using a key from Google AI Studio. Do not put API keys in the repository or
paste them into chat. `LLM_MODEL` defaults to `gemini/gemini-3.8-flash` in the
Blueprint and can be changed in Render.

The Blueprint uses Render's free plan. Free services can sleep while idle and have
limited memory. This app keeps uploaded PDFs and analysis jobs in local storage and
memory, so a restart, deploy, or sleep can clear an in-progress job; users may need
to start that analysis again. Analysis also requires the configured hosted LLM
provider, and model latency or rate limits still apply.

---

## Usage

1. Search a research topic in **Discover Research Papers** to find scholarly records from Crossref and arXiv.
2. Select up to three arXiv preprints and choose **Download & analyse** to retrieve their PDFs directly into the existing analysis pipeline. PDF downloads are size-limited and verified.
3. For other records, use the DOI/publisher links and upload a PDF via the drag-and-drop zone. A Crossref PDF link does not guarantee free access.
4. Click **Analyse** for uploaded files.
5. Watch the research agents work (live progress indicator)
6. Explore results across 5 tabs:
   - **Papers** — summaries and structured key findings with quotations checked against the source page
   - **Concept Map** — interactive D3 force-directed graph (drag, zoom, click nodes)
   - **Literature Review** — side-by-side structured evidence matrix plus the cross-paper synthesis
   - **Future Directions** — three evidence-grounded study proposals, each with a question, gap, design, and evaluation plan
   - **Ask Papers** — ask questions across the PDFs and open cited passages in their original pages
7. Download a Markdown report for reading/sharing or JSON for further analysis and reuse.

The evidence matrix is a navigation and comparison aid, not a meta-analysis. Check
the linked source pages before relying on extracted claims or comparing results
across different datasets, methods, or evaluation settings.
Downloaded reports remain on your device; links that open papers in the live app
only work while that analysis job and its uploaded PDFs are still available on the
server.

Question answering uses local lexical passage retrieval over up to 250,000 extracted
characters per paper. Quotations are checked against the original page text before
they are returned. Uploaded files and analysis jobs are held in memory/local storage
for the lifetime of the backend process; restarting the server clears job state.
Ask Papers is tuned for concise answers, typically 2-4 sentences, with short
per-paper bullets for comparisons.

Paper discovery uses Crossref and arXiv public APIs and requires no API key. Search
coverage is not exhaustive. Direct PDF analysis is currently supported for arXiv
papers; publisher or DOI pages may require institutional access. Search and download
availability depends on the external services.

---

## Sample Papers

Two sample papers are included in `samples/` to make the demo quick to run:

```
samples/
  attention_is_all_you_need.pdf    # Transformer architecture paper
  bert_pretraining.pdf             # BERT language model paper
```

---

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/search` | Search Crossref and arXiv metadata |
| `POST` | `/analyze-discovered` | Download and analyze 1-3 selected arXiv PDFs |
| `POST` | `/upload` | Upload 1-3 PDFs, get `session_id` |
| `POST` | `/analyze` | Start analysis, get `job_id` |
| `GET` | `/progress/{job_id}` | Poll agent progress |
| `GET` | `/results/{job_id}` | Fetch full results JSON |
| `POST` | `/ask/{job_id}` | Ask a question and receive verified paper/page quotations |
| `GET` | `/papers/{job_id}/{paper_index}` | Open an uploaded PDF inline for citation verification |

Interactive API documentation is available at `/docs` when the backend is running.

---

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI endpoints
│   ├── models.py            # Pydantic schemas
│   ├── crew.py              # ResearchCrew orchestrator
│   ├── qa.py                # Passage retrieval and citation verification
│   ├── agents/
│   │   ├── ingestion_agent.py
│   │   ├── summarizer_agent.py
│   │   ├── findings_agent.py
│   │   ├── synthesis_agent.py
│   │   └── future_agent.py
│   └── tools/
│       └── pdf_tool.py      # Custom CrewAI BaseTool (pdfplumber)
├── frontend/
│   └── src/
│       ├── App.jsx          # State machine + polling
│       ├── api.js           # API client
│       └── components/
│           ├── UploadZone.jsx
│           ├── ProgressTracker.jsx
│           ├── PaperSummary.jsx
│           ├── KeyFindings.jsx
│           ├── LitReview.jsx    # Narrative synthesis + evidence matrix
│           ├── ConceptMap.jsx   ← D3 force graph
│           ├── FutureDirections.jsx
│           └── AskPapers.jsx    # Source-grounded questions and citations
├── samples/                 # Demo PDFs
├── .env.example
├── requirements.txt
└── README.md
```

---

## Future Work

- **PPTX / Slide Generation** — Automatically generate a presentation summarising the analysis results. (Explicitly out of scope for this build.)
- **Background Job Queue** — Celery + Redis for production-grade async job handling, allowing multiple concurrent analyses.
- **Citation Graph** — Parse reference lists and build a citation-relationship graph across papers.
- **Persistent research projects** — Save paper libraries, questions, and analyses across server restarts.
- **Export** — Download results as PDF, Markdown, or structured JSON.

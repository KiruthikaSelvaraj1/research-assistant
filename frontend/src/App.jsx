import { useState, useEffect, useCallback, useRef } from 'react'
import { uploadPapers, startAnalysis, getProgress, getResults } from './api'
import { UploadZone } from './components/UploadZone'
import { ProgressTracker } from './components/ProgressTracker'
import { PaperSummary } from './components/PaperSummary'
import { KeyFindings } from './components/KeyFindings'
import { LitReview } from './components/LitReview'
import { ConceptMap } from './components/ConceptMap'
import { FutureDirections } from './components/FutureDirections'

// View state machine: idle → uploading → analyzing → results
const VIEWS = { IDLE: 'idle', UPLOADING: 'uploading', ANALYZING: 'analyzing', RESULTS: 'results' }
const TABS = ['Papers', 'Concept Map', 'Literature Review', 'Future Directions']

export default function App() {
  const [view, setView] = useState(VIEWS.IDLE)
  const [activeTab, setActiveTab] = useState(0)
  const [sessionId, setSessionId] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [progress, setProgress] = useState([])
  const [jobStatus, setJobStatus] = useState('queued')
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const pollRef = useRef(null)

  // ── Upload ────────────────────────────────────────────────────────────────
  const handleUploadAndAnalyze = useCallback(async (files) => {
    setError(null)
    try {
      setView(VIEWS.UPLOADING)
      const upRes = await uploadPapers(files)
      setSessionId(upRes.session_id)

      const anRes = await startAnalysis(upRes.session_id)
      setJobId(anRes.job_id)
      setView(VIEWS.ANALYZING)
    } catch (e) {
      setError(e.message)
      setView(VIEWS.IDLE)
    }
  }, [])

  // ── Polling ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (view !== VIEWS.ANALYZING || !jobId) return

    const poll = async () => {
      try {
        const prog = await getProgress(jobId)
        setProgress(prog.progress || [])
        setJobStatus(prog.status)

        if (prog.status === 'complete') {
          clearInterval(pollRef.current)
          const res = await getResults(jobId)
          setResults(res)
          setView(VIEWS.RESULTS)
        } else if (prog.status === 'error') {
          clearInterval(pollRef.current)
          setError(prog.error || 'Analysis failed.')
          setView(VIEWS.IDLE)
        }
      } catch (e) {
        // Network blip — keep polling
      }
    }

    poll() // immediate first check
    pollRef.current = setInterval(poll, 2500)
    return () => clearInterval(pollRef.current)
  }, [view, jobId])

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleReset = () => {
    clearInterval(pollRef.current)
    setView(VIEWS.IDLE)
    setSessionId(null)
    setJobId(null)
    setProgress([])
    setJobStatus('queued')
    setResults(null)
    setError(null)
    setActiveTab(0)
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="app">
      {/* Hero Header */}
      <header className="app-header">
        <div className="header-content">
          <div className="logo">
            <span className="logo-icon">🧠</span>
            <div>
              <h1 className="app-title gradient-text">AI Research Assistant</h1>
              <p className="app-subtitle">Multi-agent analysis powered by CrewAI + your configured LLM</p>
            </div>
          </div>
          {view === VIEWS.RESULTS && (
            <button className="btn btn-ghost" onClick={handleReset}>
              ← New Analysis
            </button>
          )}
        </div>
        <div className="agent-badges">
          {['PDF Extraction', 'Paper Analysis', 'Comparative Synthesis', 'Future Directions'].map(a => (
            <span key={a} className="badge">{a}</span>
          ))}
        </div>
      </header>

      <main className="app-main">
        {/* Error banner */}
        {error && (
          <div className="error-banner">
            <span>⚠️</span>
            <p>{error}</p>
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}

        {/* IDLE / UPLOADING */}
        {(view === VIEWS.IDLE || view === VIEWS.UPLOADING) && (
          <div className="upload-section">
            <div className="upload-hero">
              <h2 className="section-title">Upload Research Papers</h2>
              <p className="section-desc">
                Upload 1-3 academic PDFs. Our research pipeline will
                analyse them, compare findings, synthesise a literature review, and
                map the conceptual relationships.
              </p>
            </div>
            <UploadZone
              onAnalyze={handleUploadAndAnalyze}
              disabled={view === VIEWS.UPLOADING}
            />
            <div className="feature-grid">
              {[
                { icon: '📄', title: 'Per-Paper Summaries', desc: '150-200 word summaries capturing methodology and key results' },
                { icon: '🔍', title: 'Key Findings Extraction', desc: 'Structured JSON: claims, methods, metrics, and limitations per paper' },
                { icon: '📚', title: 'Literature Review', desc: 'Cross-paper synthesis identifying agreements, conflicts, and gaps' },
                { icon: '🕸️', title: 'Interactive Concept Map', desc: 'Force-directed graph of themes, papers, and their relationships' },
                { icon: '🚀', title: 'Future Directions', desc: 'Three concrete research proposals grounded in the evidence' },
                { icon: '⚡', title: 'Faster Analysis Pipeline', desc: 'Local PDF extraction and combined per-paper analysis reduce model calls' },
              ].map(f => (
                <div key={f.title} className="feature-card glass-card">
                  <span className="feature-icon">{f.icon}</span>
                  <h3>{f.title}</h3>
                  <p>{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ANALYZING */}
        {view === VIEWS.ANALYZING && (
          <div className="analyzing-section">
            <ProgressTracker progress={progress} status={jobStatus} />
          </div>
        )}

        {/* RESULTS */}
        {view === VIEWS.RESULTS && results && (
          <div className="results-section">
            {/* Tab nav */}
            <div className="tab-nav">
              {TABS.map((tab, i) => (
                <button
                  key={tab}
                  className={`tab-btn ${activeTab === i ? 'active' : ''}`}
                  onClick={() => setActiveTab(i)}
                >
                  {tab}
                  {i === 0 && <span className="tab-count">{results.papers?.length}</span>}
                </button>
              ))}
            </div>

            <div className="tab-content">
              {/* Tab 0: Papers */}
              {activeTab === 0 && (
                <div className="papers-grid">
                  {results.papers?.map(paper => (
                    <div key={paper.paper_index}>
                      <PaperSummary paper={paper} />
                      <KeyFindings paper={paper} />
                    </div>
                  ))}
                </div>
              )}

              {/* Tab 1: Concept Map */}
              {activeTab === 1 && (
                <div>
                  <div className="section-header">
                    <h2 className="gradient-text">Research Concept Map</h2>
                    <p className="section-desc">
                      An interactive force-directed graph mapping relationships between papers,
                      concepts, and themes. Drag nodes to explore. Click a node for details.
                    </p>
                  </div>
                  <ConceptMap data={results.concept_map} />
                </div>
              )}

              {/* Tab 2: Literature Review */}
              {activeTab === 2 && (
                <LitReview text={results.lit_review} papers={results.papers} />
              )}

              {/* Tab 3: Future Directions */}
              {activeTab === 3 && (
                <FutureDirections text={results.future_directions} />
              )}
            </div>
          </div>
        )}
      </main>

      <footer className="app-footer">
        <p>Built with CrewAI · FastAPI · React · D3</p>
      </footer>
    </div>
  )
}

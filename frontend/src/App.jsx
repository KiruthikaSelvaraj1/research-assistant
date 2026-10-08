import { useState, useEffect, useCallback, useRef } from 'react'
import { uploadPapers, startAnalysis, analyzeDiscoveredPapers, getProgress, getResults } from './api'
import { UploadZone } from './components/UploadZone'
import { ProgressTracker } from './components/ProgressTracker'
import { PaperSummary } from './components/PaperSummary'
import { KeyFindings } from './components/KeyFindings'
import { LitReview } from './components/LitReview'
import { ConceptMap } from './components/ConceptMap'
import { FutureDirections } from './components/FutureDirections'
import { AskPapers } from './components/AskPapers'
import { PaperSearch } from './components/PaperSearch'
import { downloadAnalysisReport } from './report'

// View state machine: idle → uploading → analyzing → results
const VIEWS = { IDLE: 'idle', UPLOADING: 'uploading', ANALYZING: 'analyzing', RESULTS: 'results' }
const TABS = ['Papers', 'Concept Map', 'Literature Review', 'Future Directions', 'Ask Papers']

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

  useEffect(() => {
    const savedJobId = new URLSearchParams(window.location.search).get('job')
    if (!savedJobId) return

    let active = true
    setJobId(savedJobId)
    getProgress(savedJobId)
      .then(async job => {
        if (!active) return
        setProgress(job.progress || [])
        setJobStatus(job.status)
        if (job.status === 'complete') {
          const savedResults = await getResults(savedJobId)
          if (!active) return
          setResults(savedResults)
          setView(VIEWS.RESULTS)
        } else if (job.status === 'error') {
          setError(job.error || 'Analysis failed.')
          setView(VIEWS.IDLE)
        } else {
          setView(VIEWS.ANALYZING)
        }
      })
      .catch(e => {
        if (!active) return
        setError(e.message)
        setView(VIEWS.IDLE)
      })

    return () => { active = false }
  }, [])

  // ── Upload ────────────────────────────────────────────────────────────────
  const handleUploadAndAnalyze = useCallback(async (files) => {
    setError(null)
    try {
      setView(VIEWS.UPLOADING)
      const upRes = await uploadPapers(files)
      setSessionId(upRes.session_id)

      const anRes = await startAnalysis(upRes.session_id)
      setJobId(anRes.job_id)
      window.history.replaceState({}, '', `?job=${encodeURIComponent(anRes.job_id)}`)
      setView(VIEWS.ANALYZING)
    } catch (e) {
      setError(e.message)
      setView(VIEWS.IDLE)
    }
  }, [])

  const handleAnalyzeDiscovered = useCallback(async (arxivIds) => {
    setError(null)
    setView(VIEWS.UPLOADING)
    try {
      const analysis = await analyzeDiscoveredPapers(arxivIds)
      setJobId(analysis.job_id)
      window.history.replaceState({}, '', `?job=${encodeURIComponent(analysis.job_id)}`)
      setView(VIEWS.ANALYZING)
    } catch (e) {
      setError(e.message)
      setView(VIEWS.IDLE)
    }
  }, [])

  // ── Polling ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (view !== VIEWS.ANALYZING || !jobId) return

    let active = true
    const poll = async () => {
      let nextDelay = 2500
      try {
        const prog = await getProgress(jobId)
        if (!active) return
        setProgress(prog.progress || [])
        setJobStatus(prog.status)

        if (prog.status === 'complete') {
          const res = await getResults(jobId)
          if (!active) return
          setResults(res)
          setView(VIEWS.RESULTS)
          return
        } else if (prog.status === 'error') {
          setError(prog.error || 'Analysis failed.')
          setView(VIEWS.IDLE)
          return
        }
      } catch (e) {
        nextDelay = 5000
      }
      if (active) pollRef.current = setTimeout(poll, nextDelay)
    }

    poll()
    return () => {
      active = false
      clearTimeout(pollRef.current)
    }
  }, [view, jobId])

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleReset = () => {
    clearTimeout(pollRef.current)
    window.history.replaceState({}, '', window.location.pathname)
    setView(VIEWS.IDLE)
    setSessionId(null)
    setJobId(null)
    setProgress([])
    setJobStatus('queued')
    setResults(null)
    setError(null)
    setActiveTab(0)
  }

  const handleReportDownload = (format) => {
    try {
      downloadAnalysisReport(results, format, jobId, window.location.origin)
    } catch (downloadError) {
      setError(downloadError.message || 'Could not export the analysis report.')
    }
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
            <PaperSearch
              onAnalyzeDiscovered={handleAnalyzeDiscovered}
              analyzing={view === VIEWS.UPLOADING}
            />
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
                { icon: '🔍', title: 'Evidence-Linked Findings', desc: 'Verify key claims against quotations linked to the original PDF page' },
                { icon: '📚', title: 'Literature Review', desc: 'Cross-paper synthesis identifying agreements, conflicts, and gaps' },
                { icon: '🕸️', title: 'Interactive Concept Map', desc: 'Force-directed graph of themes, papers, and their relationships' },
                { icon: '🚀', title: 'Future Directions', desc: 'Three concrete research proposals grounded in the evidence' },
                { icon: '💬', title: 'Ask Across Papers', desc: 'Ask questions and receive answers with source passages you can verify' },
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
            <div className="results-toolbar">
              <p>Download this analysis to keep or share it.</p>
              <div className="report-actions">
                <button
                  className="btn btn-ghost"
                  onClick={() => handleReportDownload('markdown')}
                >
                  Download Markdown
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => handleReportDownload('json')}
                >
                  Download JSON
                </button>
              </div>
            </div>
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
                      <KeyFindings paper={paper} jobId={jobId} />
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
                <LitReview text={results.lit_review} papers={results.papers} jobId={jobId} />
              )}

              {/* Tab 3: Future Directions */}
              {activeTab === 3 && (
                <FutureDirections text={results.future_directions} />
              )}

              {/* Keep the Q&A conversation mounted while other result tabs are open. */}
              <div style={{ display: activeTab === 4 ? 'contents' : 'none' }}>
                <AskPapers
                  jobId={jobId}
                  sourceTruncated={results.source_truncated}
                />
              </div>
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

import { useState } from 'react'

const FIELD_LABELS = {
  claim:       { icon: '💬', label: 'Claim' },
  methodology: { icon: '🔬', label: 'Methodology' },
  results:     { icon: '📊', label: 'Results & Metrics' },
  limitations: { icon: '⚠️',  label: 'Limitations' },
  significance:{ icon: '⭐', label: 'Significance' },
}

function FindingCard({ finding, index, paper, jobId }) {
  const [open, setOpen] = useState(index === 0)
  return (
    <div className={`finding-card ${open ? 'open' : ''}`}>
      <button className="finding-toggle" onClick={() => setOpen(o => !o)}>
        <span className="finding-id">{finding.finding_id || `F${index + 1}`}</span>
        <span className="finding-claim-preview">{finding.claim}</span>
        <span className="finding-chevron">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="finding-body">
          {Object.entries(FIELD_LABELS).map(([key, { icon, label }]) => (
            finding[key] ? (
              <div key={key} className="finding-field">
                <span className="field-icon">{icon}</span>
                <div>
                  <span className="field-label">{label}</span>
                  <p className="field-value">{finding[key]}</p>
                </div>
              </div>
            ) : null
          ))}
          {finding.evidence?.length > 0 && (
            <div className="finding-evidence">
              <span className="field-label">Verified source passage</span>
              {finding.evidence.map((evidence, evidenceIndex) => (
                <blockquote key={`${evidence.page}-${evidenceIndex}`}>
                  <p>“{evidence.quote}”</p>
                  <a
                    href={`/papers/${jobId}/${paper.paper_index}#page=${evidence.page}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open Paper {paper.paper_index} · page {evidence.page}
                    <span aria-hidden="true"> ↗</span>
                  </a>
                </blockquote>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function KeyFindings({ paper, jobId }) {
  if (!paper.findings || paper.findings.length === 0) return null
  return (
    <div className="key-findings glass-card">
      <h3 className="card-section-title">
        <span>🔍</span> Key Findings — Paper {paper.paper_index}
        <span className="finding-count">{paper.findings.length} findings</span>
      </h3>
      <div className="findings-list">
        {paper.findings.map((f, i) => (
          <FindingCard
            key={f.finding_id || i}
            finding={f}
            index={i}
            paper={paper}
            jobId={jobId}
          />
        ))}
      </div>
    </div>
  )
}

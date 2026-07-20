export function PaperSummary({ paper }) {
  return (
    <div className="paper-card glass-card">
      <div className="paper-card-header">
        <span className="paper-number">Paper {paper.paper_index}</span>
        <span className="paper-filename">{paper.filename}</span>
      </div>
      <div className="paper-summary-section">
        <h3 className="card-section-title">
          <span>📝</span> Summary
        </h3>
        <p className="summary-text">{paper.summary || 'Summary not available.'}</p>
      </div>
    </div>
  )
}

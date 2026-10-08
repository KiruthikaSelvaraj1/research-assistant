function EvidenceMatrix({ papers, jobId }) {
  const findings = (papers || []).flatMap(paper => (
    (paper.findings || []).map((finding, index) => ({
      paper,
      finding,
      key: finding.finding_id || `${paper.paper_index}-${index}`,
    }))
  ))

  if (findings.length === 0) return null

  return (
    <section className="comparison-section" aria-labelledby="comparison-title">
      <div className="section-header">
        <h2 id="comparison-title" className="gradient-text">Side-by-Side Evidence Matrix</h2>
        <p className="section-desc">
          Compare the extracted claims, methods, results, and reported limitations.
          This matrix uses structured findings from each paper; it adds no new claims.
        </p>
      </div>
      <div
        className="comparison-table-wrap glass-card"
        role="region"
        aria-label="Side-by-side paper evidence matrix"
        tabIndex="0"
      >
        <table className="comparison-table">
          <thead>
            <tr>
              <th scope="col">Paper</th>
              <th scope="col">Finding</th>
              <th scope="col">Method</th>
              <th scope="col">Results</th>
              <th scope="col">Limitations</th>
              <th scope="col">Source</th>
            </tr>
          </thead>
          <tbody>
            {findings.map(({ paper, finding, key }) => (
              <tr key={key}>
                <th scope="row">
                  Paper {paper.paper_index}
                  <span className="comparison-filename">{paper.filename}</span>
                </th>
                <td>{finding.claim || 'Not reported'}</td>
                <td>{finding.methodology || 'Not reported'}</td>
                <td>{finding.results || 'Not reported'}</td>
                <td>{finding.limitations || 'Not reported'}</td>
                <td>
                  {finding.evidence?.length
                    ? finding.evidence.map((evidence, evidenceIndex) => (
                      <a
                        className="comparison-source"
                        key={`${evidence.page}-${evidenceIndex}`}
                        href={`/papers/${jobId}/${paper.paper_index}#page=${evidence.page}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Page {evidence.page}
                        <span aria-hidden="true"> ↗</span>
                      </a>
                    ))
                    : 'No verified quotation'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function LitReview({ text, papers, jobId }) {
  if (!text && (!papers || papers.every(paper => !paper.findings?.length))) return null

  const sections = (text || '')
    .split(/(?=^#{1,3}\s+.+$)/m)
    .map(section => section.trim())
    .filter(Boolean)

  const renderReferences = value => value
    .split(/(\bPaper\s+\d+|\bF\d+_\d+\b)/g)
    .map((part, index) => (
      /^(Paper\s+\d+|F\d+_\d+)$/.test(part)
        ? <mark key={index} className="paper-ref">{part}</mark>
        : part
    ))

  return (
    <div className="litreview-section">
      <EvidenceMatrix papers={papers} jobId={jobId} />
      <div className="section-header">
        <h2 className="gradient-text">Synthesised Literature Review</h2>
        <p className="section-desc">
          Cross-paper analysis identifying agreements, contradictions, methodological
          differences, and open questions — synthesised by the Literature Review Agent.
        </p>
      </div>

      {/* Paper quick-ref chips */}
      {papers && papers.length > 0 && (
        <div className="paper-chips">
          {papers.map(p => (
            <span key={p.paper_index} className="paper-chip">
              Paper {p.paper_index}: {p.filename}
            </span>
          ))}
        </div>
      )}

      <div className="glass-card litreview-body">
        <div className="litreview-text">
          {sections.map((section, index) => {
            const [firstLine, ...rest] = section.split('\n')
            const heading = firstLine.match(/^#{1,3}\s+(.+)$/)
            const body = heading ? rest.join('\n').trim() : section

            return (
              <section key={index} className="litreview-subsection">
                {heading && <h3>{heading[1]}</h3>}
                {body.split(/\n\s*\n/).filter(Boolean).map((paragraph, paragraphIndex) => (
                  <p key={paragraphIndex}>{renderReferences(paragraph)}</p>
                ))}
              </section>
            )
          })}
        </div>
      </div>
    </div>
  )
}

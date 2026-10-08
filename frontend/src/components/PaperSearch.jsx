import { useState } from 'react'
import { searchPapers } from '../api'

function authorLine(authors) {
  if (!authors?.length) return 'Author information unavailable'
  const names = authors.slice(0, 4).join(', ')
  return authors.length > 4 ? `${names}, et al.` : names
}

export function PaperSearch({ onAnalyzeDiscovered, analyzing = false }) {
  const [query, setQuery] = useState('')
  const [papers, setPapers] = useState([])
  const [warnings, setWarnings] = useState([])
  const [selected, setSelected] = useState([])
  const [searched, setSearched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSearch = async (event) => {
    event.preventDefault()
    const searchText = query.trim()
    if (searchText.length < 3) {
      setError('Enter at least 3 characters to search.')
      return
    }

    setLoading(true)
    setError('')
    setSearched(false)
    setSelected([])
    setPapers([])
    setWarnings([])
    try {
      const results = await searchPapers(searchText)
      setPapers(results.papers || [])
      setWarnings(results.warnings || [])
      setSearched(true)
    } catch (err) {
      setError(err.message || 'Paper search failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const togglePaper = (arxivId) => {
    setSelected(current => current.includes(arxivId)
      ? current.filter(id => id !== arxivId)
      : current.length < 3 ? [...current, arxivId] : current)
  }

  return (
    <section className="discovery-section">
      <div className="section-header">
        <h2 className="section-title gradient-text">Discover Research Papers</h2>
        <p className="section-desc">
          Search scholarly records from Crossref and arXiv. Review abstracts,
          publication details, publisher links, and direct arXiv PDFs when available.
        </p>
      </div>

      <form className="paper-search-form" onSubmit={handleSearch}>
        <label className="sr-only" htmlFor="paper-search-query">Research topic</label>
        <input
          id="paper-search-query"
          type="search"
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder="e.g. retrieval-augmented generation for scientific literature"
          maxLength={200}
          disabled={loading || analyzing}
        />
        <button className="btn btn-primary" type="submit" disabled={loading || analyzing}>
          {analyzing
            ? <><span className="spinner" /> Preparing papers…</>
            : loading ? <><span className="spinner" /> Searching…</> : 'Search papers'}
        </button>
      </form>

      <p className="discovery-note">
        Search results combine Crossref metadata and arXiv preprints. You can select
        up to 3 arXiv papers for direct PDF analysis; other records link to their source.
      </p>

      {error && <p className="discovery-error" role="alert">{error}</p>}
      {warnings.map(warning => (
        <p className="discovery-warning" role="status" key={warning}>{warning}</p>
      ))}
      {loading && <p className="discovery-status" role="status">Searching scholarly records…</p>}
      {searched && papers.length === 0 && (
        <p className="discovery-status" role="status">
          No matching records found. Try a broader topic or different keywords.
        </p>
      )}

      {papers.length > 0 && (
        <div className="discovery-results" aria-live="polite">
          <p className="discovery-count">{papers.length} results · Crossref and arXiv</p>
          {papers.map(paper => (
            <article className="discovery-card glass-card" key={paper.paper_id}>
              <div className="discovery-card-main">
                {paper.full_text_available && paper.arxiv_id && (
                  <label className="discovery-select">
                    <input
                      type="checkbox"
                      checked={selected.includes(paper.arxiv_id)}
                      disabled={analyzing || (!selected.includes(paper.arxiv_id) && selected.length >= 3)}
                      onChange={() => togglePaper(paper.arxiv_id)}
                    />
                    Select for analysis
                  </label>
                )}
                <h3>{paper.title}</h3>
                <p className="discovery-meta">
                  {authorLine(paper.authors)}
                  {paper.year ? ` · ${paper.year}` : ''}
                  {paper.venue ? ` · ${paper.venue}` : ''}
                </p>
                {paper.abstract
                  ? <p className="discovery-abstract">{paper.abstract}</p>
                  : <p className="discovery-abstract abstract-missing">No abstract in the Crossref record.</p>}
                <p className="discovery-access">
                  {paper.full_text_available
                    ? 'arXiv offers a PDF; it will be downloaded and checked before analysis.'
                    : paper.pdf_url
                      ? 'PDF link listed by Crossref; access may vary. Upload the PDF to analyze it.'
                    : 'No direct PDF link listed; publisher access may be required.'}
                  {paper.license_url && ' License information is available.'}
                </p>
              </div>
              <div className="discovery-links">
                {paper.doi_url && (
                  <a href={paper.doi_url} target="_blank" rel="noreferrer">DOI record</a>
                )}
                {paper.arxiv_url && (
                  <a href={paper.arxiv_url} target="_blank" rel="noreferrer">arXiv record</a>
                )}
                <a href={paper.publisher_url} target="_blank" rel="noreferrer">
                  Publisher page
                </a>
                {paper.pdf_url && (
                  <a href={paper.pdf_url} target="_blank" rel="noreferrer">
                    {paper.full_text_available ? 'Open arXiv PDF' : 'Open listed PDF (access may vary)'}
                  </a>
                )}
                {paper.license_url && (
                  <a href={paper.license_url} target="_blank" rel="noreferrer">
                    License
                  </a>
                )}
              </div>
            </article>
          ))}
          {selected.length > 0 && (
            <div className="discovery-analyze">
              <button
                className="btn btn-primary"
                type="button"
                disabled={analyzing}
                onClick={() => onAnalyzeDiscovered(selected)}
              >
                {analyzing
                  ? <><span className="spinner" /> Preparing papers…</>
                  : `Download & analyse ${selected.length} selected paper${selected.length === 1 ? '' : 's'}`}
              </button>
              <p>Only verified arXiv PDF files are sent to the analysis pipeline.</p>
            </div>
          )}
        </div>
      )}

      <div className="discovery-upload">
        <h3>Have a PDF already?</h3>
        <p>Upload it below to compare findings, build a literature review, and ask cited questions.</p>
      </div>
    </section>
  )
}

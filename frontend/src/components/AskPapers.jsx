import { useState } from 'react'
import { askQuestion } from '../api'

export function AskPapers({ jobId, sourceTruncated = false }) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    const prompt = question.trim()
    if (prompt.length < 3 || loading) return

    setLoading(true)
    setError('')
    setQuestion('')
    setMessages(current => [...current, { question: prompt, pending: true }])
    try {
      const history = messages
        .filter(message => message.response)
        .slice(-4)
        .map(message => ({
          question: message.question,
          answer: message.response.answer,
        }))
      const response = await askQuestion(jobId, prompt, history)
      setMessages(current => current.map((message, index) => (
        index === current.length - 1
          ? { question: prompt, response }
          : message
      )))
    } catch (requestError) {
      setMessages(current => current.filter((_, index) => index !== current.length - 1))
      setQuestion(prompt)
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="ask-section">
      <div className="section-header">
        <h2 className="gradient-text">Ask Your Papers</h2>
        <p className="section-desc">
          Ask a question across the analyzed papers. Get a concise, evidence-grounded answer
          with quotations you can verify in the original PDF.
        </p>
      </div>

      {sourceTruncated && (
        <p className="source-limit-note">
          Text search is limited to the first 250,000 extracted characters of each paper.
        </p>
      )}

      <div className="ask-messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="ask-empty glass-card">
            <span>💡</span>
            <p>Try asking what methods the papers share, where their results differ, or what limitations they report.</p>
          </div>
        )}
        {messages.map((message, index) => (
          <article className="qa-card glass-card" key={`${index}-${message.question}`}>
            <h3 className="qa-question">You asked</h3>
            <p className="qa-question-text">{message.question}</p>
            {message.pending ? (
              <p className="qa-pending"><span className="spinner" /> Searching paper evidence…</p>
            ) : (
              <>
                <h3 className="qa-answer-heading">Answer</h3>
                <p className={message.response.abstained ? 'qa-abstained' : 'qa-answer'}>
                  {message.response.answer}
                </p>
                {message.response.citations?.length > 0 && (
                  <div className="qa-citations">
                    <h4>Verified source passages</h4>
                    {message.response.citations.map((citation, citationIndex) => (
                      <blockquote key={`${citation.paper_index}-${citation.page}-${citationIndex}`}>
                        <p>“{citation.quote}”</p>
                        <a
                          href={`/papers/${jobId}/${citation.paper_index}#page=${citation.page}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Paper {citation.paper_index} · {citation.filename} · page {citation.page}
                          <span aria-hidden="true"> ↗</span>
                        </a>
                      </blockquote>
                    ))}
                  </div>
                )}
              </>
            )}
          </article>
        ))}
      </div>

      {error && <p className="ask-error" role="alert">{error}</p>}
      <form className="ask-form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="paper-question">Ask a question about the papers</label>
        <textarea
          id="paper-question"
          value={question}
          onChange={event => setQuestion(event.target.value)}
          placeholder="Ask a question about your papers…"
          maxLength={1000}
          rows={3}
          disabled={loading}
        />
        <div className="ask-form-footer">
          <span>{question.length}/1000</span>
          <button className="btn btn-primary" type="submit" disabled={loading || question.trim().length < 3}>
            {loading ? 'Searching…' : 'Ask'}
          </button>
        </div>
      </form>
    </section>
  )
}

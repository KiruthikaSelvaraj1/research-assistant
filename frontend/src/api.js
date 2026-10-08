/**
 * api.js — thin wrapper around the FastAPI backend
 */

const BASE = ''  // Vite proxies API paths to the FastAPI backend.

export async function searchPapers(query, limit = 10) {
  const res = await fetch(`${BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Paper search failed (${res.status})`)
  }
  return res.json()
}

export async function analyzeDiscoveredPapers(arxivIds) {
  const res = await fetch(`${BASE}/analyze-discovered`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ arxiv_ids: arxivIds }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Could not prepare selected papers (${res.status})`)
  }
  return res.json()
}

export async function uploadPapers(files) {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Upload failed (${res.status})`)
  }
  return res.json()  // { session_id, filenames, message }
}

export async function startAnalysis(sessionId) {
  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Analyze failed (${res.status})`)
  }
  return res.json()  // { job_id, status, message }
}

export async function getProgress(jobId) {
  const res = await fetch(`${BASE}/progress/${jobId}`)
  if (!res.ok) throw new Error(`Progress check failed (${res.status})`)
  return res.json()  // { job_id, status, progress[], has_results, error }
}

export async function getResults(jobId) {
  const res = await fetch(`${BASE}/results/${jobId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Results fetch failed (${res.status})`)
  }
  return res.json()  // { papers[], lit_review, concept_map, future_directions }
}

export async function askQuestion(jobId, question, history = []) {
  const res = await fetch(`${BASE}/ask/${jobId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, history }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Question failed (${res.status})`)
  }
  return res.json()
}

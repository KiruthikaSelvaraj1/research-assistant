function assertAnalysisResults(results) {
  if (!results || !Array.isArray(results.papers)) {
    throw new TypeError('Analysis results are not available for export.')
  }
}

function formatEvidence(evidence, paperIndex, jobId, sourceBaseUrl) {
  if (!evidence?.length) return 'No verified source quotation was recorded.'

  return evidence.map(item => {
    const quote = item.quote
      .split(/\r?\n/)
      .map(line => `> ${line}`)
      .join('\n')
    const source = jobId
      ? `\n> [Open Paper ${paperIndex}, page ${item.page}](${sourceBaseUrl.replace(/\/$/, '')}/papers/${encodeURIComponent(jobId)}/${paperIndex}#page=${item.page})`
      : `\n> Paper ${paperIndex}, page ${item.page}`
    return `${quote}${source}`
  }).join('\n\n')
}

export function buildMarkdownReport(
  results,
  {
    jobId = '',
    generatedAt = new Date(),
    sourceBaseUrl = 'https://ai-research-assistant-as88.onrender.com',
  } = {},
) {
  assertAnalysisResults(results)

  const sections = [
    '# Research Paper Analysis',
    '',
    `Generated: ${generatedAt.toISOString()}`,
    '',
    '> AI-generated research aid. Verify claims and quotations against the original papers before relying on them.',
    '',
    '## Papers',
  ]

  for (const paper of results.papers) {
    sections.push(
      '',
      `### Paper ${paper.paper_index}: ${paper.filename}`,
      '',
      '#### Summary',
      '',
      paper.summary || 'Summary not available.',
    )

    for (const [index, finding] of (paper.findings || []).entries()) {
      sections.push(
        '',
        `#### Finding ${finding.finding_id || index + 1}: ${finding.claim || 'Untitled finding'}`,
        '',
        `- **Methodology:** ${finding.methodology || 'Not reported'}`,
        `- **Results:** ${finding.results || 'Not reported'}`,
        `- **Limitations:** ${finding.limitations || 'Not reported'}`,
        `- **Significance:** ${finding.significance || 'Not reported'}`,
        '',
        '**Verified evidence**',
        '',
        formatEvidence(finding.evidence, paper.paper_index, jobId, sourceBaseUrl),
      )
    }
  }

  sections.push('', '## Side-by-Side Comparison', '')
  if (results.papers.some(paper => paper.findings?.length)) {
    sections.push(
      '| Paper | Finding | Methodology | Results | Limitations |',
      '| --- | --- | --- | --- | --- |',
    )
    for (const paper of results.papers) {
      for (const [index, finding] of (paper.findings || []).entries()) {
        const cells = [
          `Paper ${paper.paper_index}`,
          finding.claim || `Finding ${index + 1}`,
          finding.methodology || 'Not reported',
          finding.results || 'Not reported',
          finding.limitations || 'Not reported',
        ].map(value => String(value).replace(/\|/g, '\\|').replace(/\r?\n/g, '<br>'))
        sections.push(`| ${cells.join(' | ')} |`)
      }
    }
  } else {
    sections.push('No structured findings were recorded.')
  }

  sections.push(
    '',
    '## Synthesised Literature Review',
    '',
    results.lit_review || 'Literature review not available.',
    '',
    '## Future Research Directions',
    '',
    results.future_directions || 'Future directions not available.',
    '',
    '## Concept Map',
    '',
    '```json',
    JSON.stringify(results.concept_map || { nodes: [], edges: [] }, null, 2),
    '```',
    '',
  )

  return sections.join('\n')
}

export function serializeAnalysisReport(
  results,
  format,
  { jobId = '', generatedAt = new Date(), sourceBaseUrl } = {},
) {
  assertAnalysisResults(results)

  if (format === 'json') {
    return {
      content: JSON.stringify({
        ...results,
        report_metadata: {
          generated_at: generatedAt.toISOString(),
          job_id: jobId || null,
        },
      }, null, 2),
      mimeType: 'application/json',
      extension: 'json',
    }
  }
  if (format === 'markdown') {
    return {
      content: buildMarkdownReport(results, { jobId, generatedAt, sourceBaseUrl }),
      mimeType: 'text/markdown;charset=utf-8',
      extension: 'md',
    }
  }

  throw new RangeError(`Unsupported report format: ${format}`)
}

export function downloadAnalysisReport(results, format, jobId = '', sourceBaseUrl = window.location.origin) {
  const report = serializeAnalysisReport(results, format, { jobId, sourceBaseUrl })
  const blob = new Blob([report.content], { type: report.mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `research-analysis-${new Date().toISOString().slice(0, 10)}.${report.extension}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
}

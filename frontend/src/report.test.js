import assert from 'node:assert/strict'
import test from 'node:test'
import { buildMarkdownReport, serializeAnalysisReport } from './report.js'

const generatedAt = new Date('2026-10-08T04:00:00.000Z')
const results = {
  papers: [{
    paper_index: 1,
    filename: 'sample.pdf',
    summary: 'A concise summary.',
    findings: [{
      finding_id: 'F1_1',
      claim: 'Method | result',
      methodology: 'A method',
      results: 'A result',
      limitations: 'A limit',
      significance: 'A contribution',
      evidence: [{ page: 4, quote: 'A verified source quotation.' }],
    }],
  }],
  lit_review: 'A synthesised review.',
  future_directions: 'A proposed direction.',
  concept_map: { nodes: [{ id: 'n1' }], edges: [] },
}

test('Markdown report contains findings, escaped comparison cells, and evidence links', () => {
  const report = buildMarkdownReport(results, {
    jobId: 'job 123',
    generatedAt,
    sourceBaseUrl: 'https://example.test/',
  })

  assert.match(report, /# Research Paper Analysis/)
  assert.match(report, /A concise summary\./)
  assert.match(report, /F1_1: Method \| result/)
  assert.match(report, /Method \\| result/)
  assert.match(report, /Open Paper 1, page 4/)
  assert.match(report, /https:\/\/example\.test\/papers\/job%20123\/1#page=4/)
  assert.match(report, /A synthesised review\./)
  assert.match(report, /A proposed direction\./)
  assert.match(report, /"id": "n1"/)
  assert.match(report, /AI-generated research aid/)
})

test('JSON report preserves results and adds export metadata', () => {
  const report = serializeAnalysisReport(results, 'json', { jobId: 'job-123', generatedAt })
  const parsed = JSON.parse(report.content)

  assert.equal(report.mimeType, 'application/json')
  assert.equal(report.extension, 'json')
  assert.deepEqual(parsed.papers, results.papers)
  assert.equal(parsed.report_metadata.job_id, 'job-123')
  assert.equal(parsed.report_metadata.generated_at, generatedAt.toISOString())
})

test('report serializers reject missing results and unknown formats', () => {
  assert.throws(() => serializeAnalysisReport(null, 'json'), /not available/)
  assert.throws(() => serializeAnalysisReport(results, 'pdf'), /Unsupported report format/)
})

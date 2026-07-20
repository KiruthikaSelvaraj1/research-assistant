import { useState, useRef, useCallback } from 'react'

const MAX_FILES = 3
const ACCEPTED = '.pdf'

export function UploadZone({ onAnalyze, disabled }) {
  const [files, setFiles] = useState([])
  const [dragging, setDragging] = useState(false)
  const [fileError, setFileError] = useState('')
  const inputRef = useRef(null)

  const addFiles = useCallback((incoming) => {
    setFileError('')
    const pdfs = [...incoming].filter(f => f.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length !== incoming.length) {
      setFileError('Only PDF files are accepted.')
      return
    }
    const merged = [...files, ...pdfs].slice(0, MAX_FILES)
    if (files.length + pdfs.length > MAX_FILES) {
      setFileError(`Maximum ${MAX_FILES} papers per run. Extra files were ignored.`)
    }
    setFiles(merged)
  }, [files])

  const removeFile = (idx) => setFiles(f => f.filter((_, i) => i !== idx))

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }

  const handleAnalyze = () => {
    if (files.length === 0) { setFileError('Please add at least one PDF.'); return }
    onAnalyze(files)
  }

  const formatSize = (bytes) => bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`

  return (
    <div className="upload-zone-wrapper">
      {/* Drop target */}
      <div
        className={`drop-zone ${dragging ? 'dragging' : ''} ${files.length > 0 ? 'has-files' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => files.length === 0 && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          multiple
          style={{ display: 'none' }}
          onChange={e => addFiles(e.target.files)}
        />
        {files.length === 0 ? (
          <div className="drop-prompt">
            <div className="drop-icon">📂</div>
            <p className="drop-title">Drop PDF papers here</p>
            <p className="drop-sub">or click to browse · up to {MAX_FILES} papers</p>
          </div>
        ) : (
          <div className="file-list">
            {files.map((f, i) => (
              <div key={`${f.name}-${i}`} className="file-item">
                <span className="file-icon">📄</span>
                <div className="file-info">
                  <span className="file-name">{f.name}</span>
                  <span className="file-size">{formatSize(f.size)}</span>
                </div>
                <button
                  className="file-remove"
                  onClick={e => { e.stopPropagation(); removeFile(i) }}
                  title="Remove"
                >✕</button>
              </div>
            ))}
            {files.length < MAX_FILES && (
              <button
                className="add-more-btn"
                onClick={e => { e.stopPropagation(); inputRef.current?.click() }}
              >
                + Add another paper
              </button>
            )}
          </div>
        )}
      </div>

      {fileError && <p className="upload-error">{fileError}</p>}

      {files.length > 0 && (
        <button
          className="btn btn-primary analyze-btn"
          onClick={handleAnalyze}
          disabled={disabled}
        >
          {disabled ? (
            <><span className="spinner" /> Uploading…</>
          ) : (
            <><span>🚀</span> Analyse {files.length} Paper{files.length > 1 ? 's' : ''}</>
          )}
        </button>
      )}
    </div>
  )
}

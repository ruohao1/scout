import { useEffect, useState } from 'react'
import { AlertTriangleIcon, CheckIcon, CopyIcon, DownloadIcon, FileTextIcon, RefreshCwIcon, SparklesIcon } from 'lucide-react'
import { draftTailoredCv, draftTailoredCvLatex } from '../../api.js'

export function TailoredCVPane({ jobId, selectedProfile }) {
  const [instruction, setInstruction] = useState('')
  const [draft, setDraft] = useState(null)
  const [latexDraft, setLatexDraft] = useState(null)
  const [error, setError] = useState('')
  const [latexError, setLatexError] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [isGeneratingLatex, setIsGeneratingLatex] = useState(false)
  const [copyStatus, setCopyStatus] = useState('')

  useEffect(() => {
    setDraft(null)
    setLatexDraft(null)
    setError('')
    setLatexError('')
    setInstruction('')
    setCopyStatus('')
  }, [jobId])

  async function generateDraft() {
    if (!jobId || isGenerating) return
    setIsGenerating(true)
    setError('')
    setLatexDraft(null)
    setLatexError('')
    setCopyStatus('')
    try {
      const result = await draftTailoredCv(jobId, {
        targetProfileId: selectedProfile?.id || null,
        instruction,
        evidenceLimit: 8,
      })
      setDraft(result)
    } catch (error) {
      setError(error.message)
    } finally {
      setIsGenerating(false)
    }
  }

  async function generateLatex() {
    if (!jobId || isGeneratingLatex) return
    setIsGeneratingLatex(true)
    setLatexError('')
    setCopyStatus('')
    try {
      const result = await draftTailoredCvLatex(jobId, {
        targetProfileId: selectedProfile?.id || null,
        instruction,
        evidenceLimit: 8,
      })
      setLatexDraft(result)
    } catch (error) {
      setLatexError(error.message)
    } finally {
      setIsGeneratingLatex(false)
    }
  }

  async function copyLatex() {
    if (!latexDraft?.latex) return
    try {
      await navigator.clipboard.writeText(latexDraft.latex)
      setCopyStatus('Copied LaTeX to clipboard.')
    } catch {
      setCopyStatus('Clipboard copy failed. Select and copy the LaTeX manually.')
    }
  }

  function downloadLatex() {
    if (!latexDraft?.latex) return
    const blob = new Blob([latexDraft.latex], { type: 'application/x-tex;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = latexDraft.filename || 'tailored-cv.tex'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <aside className="tailored-cv-pane" aria-label="Tailored CV draft">
      <div className="tailored-cv-scroll">
        <header className="tailored-cv-header">
          <p>Application draft</p>
          <h2>Tailor CV bullets</h2>
          <span>{selectedProfile ? `Using ${selectedProfile.name}` : 'Using candidate evidence without a target profile.'}</span>
        </header>

        <section className="tailored-cv-control" aria-label="Tailoring controls">
          <label>
            <span>Direction</span>
            <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Optional: emphasize backend projects, keep it junior, make bullets concise..." rows={4} />
          </label>
          <button type="button" onClick={generateDraft} disabled={isGenerating || !jobId}>
            {isGenerating ? <RefreshCwIcon aria-hidden="true" /> : <SparklesIcon aria-hidden="true" />}
            {isGenerating ? 'Drafting...' : draft ? 'Regenerate bullets' : 'Generate bullets'}
          </button>
          <button type="button" onClick={generateLatex} disabled={isGeneratingLatex || !jobId}>
            {isGeneratingLatex ? <RefreshCwIcon aria-hidden="true" /> : <FileTextIcon aria-hidden="true" />}
            {isGeneratingLatex ? 'Exporting...' : latexDraft ? 'Regenerate LaTeX' : 'Generate LaTeX'}
          </button>
        </section>

        {error && (
          <div className="tailored-cv-alert warning-state" role="alert">
            <AlertTriangleIcon aria-hidden="true" />
            <div>
              <strong>Could not draft CV bullets.</strong>
              <span>{error}</span>
            </div>
          </div>
        )}

        {latexError && (
          <div className="tailored-cv-alert warning-state" role="alert">
            <AlertTriangleIcon aria-hidden="true" />
            <div>
              <strong>Could not export LaTeX.</strong>
              <span>{latexError}</span>
            </div>
          </div>
        )}

        {!draft && !error && (
          <section className="tailored-cv-empty">
            <FileTextIcon aria-hidden="true" />
            <strong>Candidate RAG will choose the evidence.</strong>
            <span>Scout retrieves relevant candidate evidence for this job, then writes source-backed CV bullets you can review.</span>
          </section>
        )}

        {draft && (
          <div className="tailored-cv-result">
            <section className="tailored-cv-section">
              <p>Headline</p>
              <h3>{draft.headline}</h3>
              <span>{draft.summary}</span>
            </section>

            <section className="tailored-cv-section">
              <p>Suggested CV bullets</p>
              <ol className="tailored-cv-bullets">
                {draft.bullets.map((bullet, index) => (
                  <li key={`${bullet.text}-${index}`}>
                    <span>{bullet.text}</span>
                    {bullet.evidence_ids?.length > 0 && <small>Evidence: {bullet.evidence_ids.map(shortId).join(', ')}</small>}
                  </li>
                ))}
              </ol>
            </section>

            {draft.gaps_or_cautions?.length > 0 && (
              <section className="tailored-cv-section">
                <p>Gaps or cautions</p>
                <ul className="tailored-cv-cautions">
                  {draft.gaps_or_cautions.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </section>
            )}

            <section className="tailored-cv-section">
              <p>Evidence used</p>
              <div className="tailored-cv-evidence-list">
                {(draft.evidence_used?.length ? draft.evidence_used : draft.retrieved_evidence || []).slice(0, 6).map((item) => (
                  <article key={`${item.evidence_id}-${item.reason || item.score || ''}`} className="tailored-cv-evidence">
                    <strong>{item.title || item.type || 'Candidate evidence'}</strong>
                    <span>{[item.organization, item.location].filter(Boolean).join(' · ')}</span>
                    {item.reason && <small>{item.reason}</small>}
                  </article>
                ))}
              </div>
            </section>
          </div>
        )}

        {latexDraft && (
          <section className="tailored-cv-section tailored-cv-latex">
            <p>LaTeX export</p>
            <h3>{latexDraft.filename}</h3>
            <div className="tailored-cv-actions">
              <button type="button" onClick={copyLatex}>
                <CopyIcon aria-hidden="true" />
                Copy LaTeX
              </button>
              <button type="button" onClick={downloadLatex}>
                <DownloadIcon aria-hidden="true" />
                Download .tex
              </button>
            </div>
            {copyStatus && (
              <span className="tailored-cv-copy-status">
                <CheckIcon aria-hidden="true" />
                {copyStatus}
              </span>
            )}
            {latexDraft.warnings?.map((warning) => <small key={warning}>{warning}</small>)}
            <pre>{latexDraft.latex}</pre>
          </section>
        )}
      </div>
    </aside>
  )
}

function shortId(value) {
  return String(value).slice(0, 8)
}

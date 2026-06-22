import { useEffect, useState } from 'react'
import { AlertTriangleIcon, CheckIcon, ClipboardListIcon, CopyIcon, DownloadIcon, FileTextIcon, RefreshCwIcon, ShieldCheckIcon, SparklesIcon } from 'lucide-react'
import { draftTailoredCv, draftTailoredCvLatex, tailoredCvLatexPdfUrl } from '../../api.js'

export function TailoredCVPane({ jobId, selectedProfile, initialLatexDraft = null }) {
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
    setLatexDraft(initialLatexDraft)
    setError('')
    setLatexError('')
    setInstruction('')
    setCopyStatus('')
  }, [jobId, initialLatexDraft])

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

  const evidenceItems = evidenceForDraft(draft)
  const evidenceById = evidenceMap(evidenceItems)
  const exportState = exportStatus(latexDraft)

  return (
    <aside className="tailored-cv-pane" aria-label="Tailored CV draft">
      <div className="tailored-cv-scroll">
        <TailoredCVHeader draft={draft} latexDraft={latexDraft} selectedProfile={selectedProfile} exportState={exportState} />

        <TailoringControls
          instruction={instruction}
          isGenerating={isGenerating}
          isGeneratingLatex={isGeneratingLatex}
          hasDraft={Boolean(draft)}
          hasLatexDraft={Boolean(latexDraft)}
          canGenerate={Boolean(jobId)}
          onInstructionChange={setInstruction}
          onGenerateDraft={generateDraft}
          onGenerateLatex={generateLatex}
        />

        <Alerts error={error} latexError={latexError} />

        {!draft && !error && <EmptyTailoringState />}

        {draft && <DraftPreview draft={draft} evidenceById={evidenceById} />}

        {draft && <EvidenceMap evidenceItems={evidenceItems} />}

        <ExportPanel
          jobId={jobId}
          latexDraft={latexDraft}
          exportState={exportState}
          copyStatus={copyStatus}
          onCopyLatex={copyLatex}
          onDownloadLatex={downloadLatex}
        />
      </div>
    </aside>
  )
}

function TailoredCVHeader({ draft, latexDraft, selectedProfile, exportState }) {
  return (
    <header className="tailored-cv-header tailored-cv-hero">
      <div>
        <p>Application cockpit</p>
        <h2>Tailor CV</h2>
        <span>{selectedProfile ? `Using ${selectedProfile.name}` : 'Using candidate evidence without a target profile.'}</span>
      </div>
      <div className="tailored-cv-status-grid" aria-label="Tailoring status">
        <StatusBadge tone={draft ? 'ready' : 'idle'} label={draft ? 'Draft ready' : 'No draft'} />
        <StatusBadge tone={latexDraft ? 'ready' : 'idle'} label={latexDraft ? 'LaTeX ready' : 'No export'} />
        <StatusBadge tone={exportState.tone} label={exportState.label} />
      </div>
    </header>
  )
}

function TailoringControls({ instruction, isGenerating, isGeneratingLatex, hasDraft, hasLatexDraft, canGenerate, onInstructionChange, onGenerateDraft, onGenerateLatex }) {
  return (
    <section className="tailored-cv-control tailored-cv-command" aria-label="Tailoring controls">
      <label>
        <span>Direction</span>
        <textarea value={instruction} onChange={(event) => onInstructionChange(event.target.value)} placeholder="Optional: emphasize backend projects, keep it junior, make bullets concise..." rows={4} />
      </label>
      <div className="tailored-cv-command-actions">
        <button type="button" onClick={onGenerateDraft} disabled={isGenerating || !canGenerate}>
          {isGenerating ? <RefreshCwIcon aria-hidden="true" /> : <SparklesIcon aria-hidden="true" />}
          {isGenerating ? 'Drafting...' : hasDraft ? 'Regenerate bullets' : 'Generate bullets'}
        </button>
        <button type="button" onClick={onGenerateLatex} disabled={isGeneratingLatex || !canGenerate}>
          {isGeneratingLatex ? <RefreshCwIcon aria-hidden="true" /> : <FileTextIcon aria-hidden="true" />}
          {isGeneratingLatex ? 'Exporting...' : hasLatexDraft ? 'Regenerate LaTeX' : 'Generate LaTeX'}
        </button>
      </div>
    </section>
  )
}

function Alerts({ error, latexError }) {
  return (
    <>
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
    </>
  )
}

function EmptyTailoringState() {
  return (
    <section className="tailored-cv-empty tailored-cv-empty-cockpit">
      <FileTextIcon aria-hidden="true" />
      <strong>Candidate RAG will choose the evidence.</strong>
      <span>Generate bullets to review final CV copy, linked evidence, cautions, and export readiness before submitting.</span>
    </section>
  )
}

function DraftPreview({ draft, evidenceById }) {
  return (
    <div className="tailored-cv-result tailored-cv-preview">
      <section className="tailored-cv-section tailored-cv-preview-card">
        <p>CV preview</p>
        <h3>{draft.headline}</h3>
        <span>{draft.summary}</span>
      </section>

      <section className="tailored-cv-section tailored-cv-bullet-review">
        <p>Bullet review</p>
        <ol className="tailored-cv-bullets">
          {draft.bullets.map((bullet, index) => (
            <li key={`${bullet.text}-${index}`}>
              <span>{bullet.text}</span>
              <BulletEvidence evidenceIds={bullet.evidence_ids || []} evidenceById={evidenceById} />
            </li>
          ))}
        </ol>
      </section>

      {draft.gaps_or_cautions?.length > 0 && (
        <section className="tailored-cv-section tailored-cv-caution-panel">
          <p>Gaps or cautions</p>
          <ul className="tailored-cv-cautions">
            {draft.gaps_or_cautions.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
      )}
    </div>
  )
}

function BulletEvidence({ evidenceIds, evidenceById }) {
  const linkedEvidence = evidenceIds.map((id) => evidenceById.get(String(id))).filter(Boolean)
  if (!linkedEvidence.length) {
    return <small>No linked evidence returned for this bullet.</small>
  }
  return (
    <div className="tailored-cv-bullet-evidence">
      {linkedEvidence.map((item) => (
        <span key={item.evidence_id || item.title} className="tailored-cv-evidence-chip">
          {item.title || item.type || 'Evidence'}
        </span>
      ))}
    </div>
  )
}

function EvidenceMap({ evidenceItems }) {
  if (!evidenceItems.length) return null
  return (
    <section className="tailored-cv-section tailored-cv-evidence-map">
      <p>Evidence map</p>
      <div className="tailored-cv-evidence-list">
        {evidenceItems.slice(0, 8).map((item) => (
          <article key={`${item.evidence_id}-${item.reason || item.score || ''}`} className="tailored-cv-evidence">
            <div className="tailored-cv-evidence-topline">
              <strong>{item.title || item.type || 'Candidate evidence'}</strong>
              <span>{item.type || 'evidence'}</span>
            </div>
            <span>{evidenceSubtitle(item)}</span>
            {item.reason && <small>{item.reason}</small>}
            {item.skills?.length > 0 && (
              <div className="tailored-cv-skill-strip">
                {item.skills.slice(0, 6).map((skill) => <em key={skill}>{skill}</em>)}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}

function ExportPanel({ jobId, latexDraft, exportState, copyStatus, onCopyLatex, onDownloadLatex }) {
  return (
    <section className="tailored-cv-section tailored-cv-latex tailored-cv-export-panel">
      <div className="tailored-cv-export-heading">
        <div>
          <p>Export</p>
          <h3>{latexDraft?.filename || 'LaTeX export not generated yet'}</h3>
        </div>
        <StatusBadge tone={exportState.tone} label={exportState.label} />
      </div>

      {latexDraft?.selected_length && (
        <div className="tailored-cv-length-card">
          <ShieldCheckIcon aria-hidden="true" />
          <div>
            <strong>{formatSelectedLength(latexDraft.selected_length)} layout</strong>
            <span>{latexDraft.length_reason}</span>
          </div>
        </div>
      )}

      <div className="tailored-cv-actions">
        <button type="button" onClick={onCopyLatex} disabled={!latexDraft?.latex}>
          <CopyIcon aria-hidden="true" />
          Copy LaTeX
        </button>
        <button type="button" onClick={onDownloadLatex} disabled={!latexDraft?.latex}>
          <DownloadIcon aria-hidden="true" />
          Download .tex
        </button>
        {latexDraft?.pdf_available && latexDraft.artifact_id && (
          <a href={tailoredCvLatexPdfUrl(jobId, latexDraft.artifact_id)} download={latexDraft.pdf_filename || undefined}>
            <DownloadIcon aria-hidden="true" />
            Download PDF
          </a>
        )}
      </div>

      {latexDraft && <LatexPipelineStatus latexDraft={latexDraft} />}

      {copyStatus && (
        <span className="tailored-cv-copy-status">
          <CheckIcon aria-hidden="true" />
          {copyStatus}
        </span>
      )}

      {latexDraft?.warnings?.length > 0 && (
        <div className="tailored-cv-warning-stack">
          {latexDraft.warnings.map((warning) => <small key={warning}>{warning}</small>)}
        </div>
      )}

      {latexDraft?.latex && (
        <details className="tailored-cv-source">
          <summary>
            <ClipboardListIcon aria-hidden="true" />
            Raw LaTeX source
          </summary>
          <pre>{latexDraft.latex}</pre>
        </details>
      )}
    </section>
  )
}

function StatusBadge({ tone, label }) {
  return <span className="tailored-cv-status-badge" data-tone={tone}>{label}</span>
}

function LatexPipelineStatus({ latexDraft }) {
  const validation = latexDraft.validation
  const compileResult = latexDraft.compile
  if (!validation && !compileResult) return null

  return (
    <div className="tailored-cv-pipeline-status">
      {validation && (
        <span className={validation.valid ? 'success-state' : 'warning-state'}>
          {validation.valid ? 'Validation passed' : 'Validation failed'}
        </span>
      )}
      {validation?.issues?.length > 0 && (
        <ul>
          {validation.issues.map((issue) => <li key={issue}>{issue}</li>)}
        </ul>
      )}
      {compileResult && (
        <span className={compileResult.success ? 'success-state' : 'warning-state'}>
          {compileResult.success ? 'PDF compiled' : 'PDF compilation failed'}
        </span>
      )}
      {compileResult?.errors?.length > 0 && (
        <ul>
          {compileResult.errors.map((error) => <li key={error}>{error}</li>)}
        </ul>
      )}
    </div>
  )
}

function evidenceForDraft(draft) {
  if (!draft) return []
  const items = draft.evidence_used?.length ? draft.evidence_used : draft.retrieved_evidence || []
  const seen = new Set()
  const unique = []
  for (const item of items) {
    const key = String(item.evidence_id || item.chunk_id || item.title || '')
    if (!key || seen.has(key)) continue
    seen.add(key)
    unique.push(item)
  }
  return unique
}

function evidenceMap(items) {
  const map = new Map()
  for (const item of items) {
    if (item.evidence_id) {
      map.set(String(item.evidence_id), item)
    }
  }
  return map
}

function exportStatus(latexDraft) {
  if (!latexDraft) return { tone: 'idle', label: 'Not exported' }
  if (latexDraft.pdf_available) return { tone: 'ready', label: 'PDF ready' }
  if (latexDraft.compiled === false) return { tone: 'warn', label: 'Source ready' }
  return { tone: 'ready', label: 'Export ready' }
}

function evidenceSubtitle(item) {
  return [item.organization, item.location, dateRange(item)].filter(Boolean).join(' · ') || 'Candidate evidence'
}

function dateRange(item) {
  const start = item.start_date
  const end = item.end_date || (item.is_current ? 'Present' : '')
  return [start, end].filter(Boolean).join(' - ')
}

function formatSelectedLength(value) {
  return String(value || '').replace(/_/g, ' ')
}

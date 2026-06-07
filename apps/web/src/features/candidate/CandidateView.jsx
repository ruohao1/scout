import { useEffect, useMemo, useState } from 'react'
import {
  createCandidateEvidence,
  deleteCandidateEvidence,
  getCandidate,
  listCandidateDocuments,
  listCandidateEvidence,
  updateCandidate,
  updateCandidateEvidence,
  uploadCandidateDocument,
} from '../../api.js'
import { blankToNull, csvValues } from '../../lib/forms.js'

const EVIDENCE_TYPES = [
  ['experience', 'Experience'],
  ['project', 'Projects'],
  ['skill', 'Skills'],
  ['education', 'Education'],
  ['certification', 'Certifications'],
  ['language', 'Languages'],
  ['interest', 'Interests'],
  ['document_note', 'Document notes'],
]

export function CandidateView() {
  const [candidate, setCandidate] = useState(null)
  const [documents, setDocuments] = useState([])
  const [evidence, setEvidence] = useState([])
  const [query, setQuery] = useState('')
  const [reviewOnly, setReviewOnly] = useState(false)
  const [editor, setEditor] = useState(null)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    loadCandidateWorkspace()
  }, [])

  const filteredEvidence = useMemo(() => filterEvidence(evidence, query, reviewOnly), [evidence, query, reviewOnly])
  const latestDocument = documents[0] || null
  const lowConfidenceCount = evidence.filter((item) => isReviewCandidate(item)).length

  async function loadCandidateWorkspace() {
    setIsLoading(true)
    setError('')
    try {
      const [candidateResult, documentResult, evidenceResult] = await Promise.allSettled([
        getCandidate(),
        listCandidateDocuments({ limit: 100 }),
        listCandidateEvidence({ limit: 1000 }),
      ])
      if (candidateResult.status === 'fulfilled') setCandidate(candidateResult.value)
      if (candidateResult.status === 'rejected' && candidateResult.reason?.message !== 'Candidate not found') setError(candidateResult.reason.message)
      if (documentResult.status === 'fulfilled') setDocuments(documentResult.value)
      if (documentResult.status === 'rejected') setError(documentResult.reason.message)
      if (evidenceResult.status === 'fulfilled') setEvidence(evidenceResult.value)
      if (evidenceResult.status === 'rejected') setError(evidenceResult.reason.message)
    } finally {
      setIsLoading(false)
    }
  }

  async function saveCandidate(payload) {
    await runSaving(async () => {
      setCandidate(await updateCandidate(payload))
    })
  }

  async function uploadDocument(file) {
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    formData.append('extract_profile', 'true')
    await runSaving(async () => {
      await uploadCandidateDocument(formData)
      await loadCandidateWorkspace()
    })
  }

  async function saveEvidence(payload, evidenceId = null) {
    await runSaving(async () => {
      if (evidenceId) await updateCandidateEvidence(evidenceId, payload)
      else await createCandidateEvidence(payload)
      setEvidence(await listCandidateEvidence({ limit: 1000 }))
      setEditor(null)
    })
  }

  async function removeEvidence(evidenceId) {
    await runSaving(async () => {
      await deleteCandidateEvidence(evidenceId)
      setEvidence(await listCandidateEvidence({ limit: 1000 }))
      setEditor(null)
    })
  }

  async function runSaving(action) {
    setIsSaving(true)
    setError('')
    try {
      await action()
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <section className="candidate-dossier" aria-label="Candidate knowledge dossier">
      <CandidateHero
        candidate={candidate}
        documents={documents}
        evidenceCount={evidence.length}
        lowConfidenceCount={lowConfidenceCount}
        latestDocument={latestDocument}
        query={query}
        reviewOnly={reviewOnly}
        isSaving={isSaving}
        onQueryChange={setQuery}
        onReviewOnlyChange={setReviewOnly}
        onAddEvidence={() => setEditor({ mode: 'create', type: 'experience', item: null })}
        onUploadDocument={uploadDocument}
        onSaveCandidate={saveCandidate}
      />

      {error && (
        <div className="candidate-alert" role="alert">
          <strong>Candidate action failed.</strong>
          <span>{error}</span>
        </div>
      )}

      {isLoading && !evidence.length && <div className="candidate-alert"><strong>Loading dossier...</strong><span>Collecting candidate documents and evidence.</span></div>}

      <div className="candidate-section-stack">
        {EVIDENCE_TYPES.map(([type, label]) => (
          <EvidenceSection
            key={type}
            type={type}
            label={label}
            items={filteredEvidence.filter((item) => item.type === type)}
            onAdd={() => setEditor({ mode: 'create', type, item: null })}
            onEdit={(item) => setEditor({ mode: 'edit', type: item.type, item })}
          />
        ))}
      </div>

      {editor && (
        <EvidenceEditor
          editor={editor}
          isSaving={isSaving}
          onClose={() => setEditor(null)}
          onSave={saveEvidence}
          onDelete={removeEvidence}
        />
      )}
    </section>
  )
}

function CandidateHero({ candidate, documents, evidenceCount, lowConfidenceCount, latestDocument, query, reviewOnly, isSaving, onQueryChange, onReviewOnlyChange, onAddEvidence, onUploadDocument, onSaveCandidate }) {
  const [isEditingIdentity, setIsEditingIdentity] = useState(false)

  return (
    <header className="candidate-hero">
      <div className="candidate-hero-copy">
        <p>Candidate dossier</p>
        <h1>{candidate?.display_name || 'Base knowledge'}</h1>
        <span>{candidate?.headline || 'A source-backed knowledge base for one candidate.'}</span>
        {candidate?.summary && <blockquote>{candidate.summary}</blockquote>}
      </div>
      <div className="candidate-hero-panel">
        <div className="candidate-stat-grid">
          <Stat label="Evidence" value={evidenceCount} />
          <Stat label="Documents" value={documents.length} />
          <Stat label="Review" value={lowConfidenceCount} />
        </div>
        <small>{latestDocument ? `Latest source: ${latestDocument.filename || latestDocument.source}` : 'No source documents uploaded yet.'}</small>
        <div className="candidate-action-row">
          <button type="button" onClick={onAddEvidence}>Add evidence</button>
          <DocumentUpload disabled={isSaving} onUpload={onUploadDocument} />
          <button type="button" data-secondary="true" onClick={() => setIsEditingIdentity((current) => !current)}>{isEditingIdentity ? 'Close identity' : 'Edit identity'}</button>
        </div>
        <div className="candidate-filter-row">
          <input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Search candidate knowledge..." />
          <label><input type="checkbox" checked={reviewOnly} onChange={(event) => onReviewOnlyChange(event.target.checked)} />Needs review</label>
        </div>
        {isEditingIdentity && <CandidateIdentityForm candidate={candidate} isSaving={isSaving} onSave={async (payload) => { await onSaveCandidate(payload); setIsEditingIdentity(false) }} />}
      </div>
    </header>
  )
}

function Stat({ label, value }) {
  return <div className="candidate-stat"><strong>{value}</strong><span>{label}</span></div>
}

function DocumentUpload({ disabled, onUpload }) {
  function handleChange(event) {
    const file = event.target.files?.[0]
    if (file) onUpload(file)
    event.target.value = ''
  }

  return (
    <label className="candidate-upload-button">
      <input type="file" accept="application/pdf,.pdf" disabled={disabled} onChange={handleChange} />
      <span>{disabled ? 'Uploading...' : 'Upload document'}</span>
    </label>
  )
}

function CandidateIdentityForm({ candidate, isSaving, onSave }) {
  const [form, setForm] = useState(() => ({
    display_name: candidate?.display_name || '',
    headline: candidate?.headline || '',
    summary: candidate?.summary || '',
  }))

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function submit(event) {
    event.preventDefault()
    onSave({
      display_name: blankToNull(form.display_name),
      headline: blankToNull(form.headline),
      summary: blankToNull(form.summary),
    })
  }

  return (
    <form className="candidate-identity-form" onSubmit={submit}>
      <label>Name<input value={form.display_name} onChange={(event) => updateField('display_name', event.target.value)} /></label>
      <label>Headline<input value={form.headline} onChange={(event) => updateField('headline', event.target.value)} /></label>
      <label>Summary<textarea rows="3" value={form.summary} onChange={(event) => updateField('summary', event.target.value)} /></label>
      <button type="submit" disabled={isSaving}>{isSaving ? 'Saving...' : 'Save identity'}</button>
    </form>
  )
}

function EvidenceSection({ type, label, items, onAdd, onEdit }) {
  return (
    <section className="candidate-evidence-section">
      <div className="candidate-section-heading">
        <div><p>{type.replace('_', ' ')}</p><h2>{label}</h2></div>
        <div><span>{items.length}</span><button type="button" onClick={onAdd}>Add</button></div>
      </div>
      {items.length === 0 ? (
        <p className="candidate-empty-section">No {label.toLowerCase()} evidence in this view.</p>
      ) : (
        <div className="candidate-evidence-grid">
          {items.map((item) => <EvidenceCard item={item} key={item.id} onEdit={() => onEdit(item)} />)}
        </div>
      )}
    </section>
  )
}

function EvidenceCard({ item, onEdit }) {
  return (
    <article className="candidate-evidence-card" data-review={isReviewCandidate(item)}>
      <button type="button" onClick={onEdit}>
        <div className="candidate-card-topline"><span>{item.type.replace('_', ' ')}</span>{isReviewCandidate(item) && <strong>Review</strong>}</div>
        <h3>{item.title}</h3>
        <p>{[item.organization, item.location, dateRange(item)].filter(Boolean).join(' / ') || 'Candidate evidence'}</p>
        {item.description && <blockquote>{item.description}</blockquote>}
        {item.skills?.length > 0 && <div className="candidate-tag-row">{item.skills.slice(0, 8).map((skill) => <span key={skill}>{skill}</span>)}</div>}
        <small>{item.source_document_id ? 'Source-backed' : 'Manual or unsourced'} · confidence {Number(item.confidence ?? 1).toFixed(1)}</small>
      </button>
    </article>
  )
}

function EvidenceEditor({ editor, isSaving, onClose, onSave, onDelete }) {
  const item = editor.item
  const [form, setForm] = useState(() => evidenceToForm(item, editor.type))

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    await onSave({
      type: form.type,
      title: form.title.trim(),
      organization: blankToNull(form.organization),
      location: blankToNull(form.location),
      start_date: blankToNull(form.start_date),
      end_date: form.is_current ? null : blankToNull(form.end_date),
      is_current: form.is_current,
      description: blankToNull(form.description),
      skills: csvValues(form.skills),
      url: blankToNull(form.url),
      metadata: item?.metadata || {},
      source_document_id: item?.source_document_id || null,
      confidence: clamp01(form.confidence),
    }, item?.id || null)
  }

  return (
    <div className="candidate-editor-backdrop" role="presentation">
      <aside className="candidate-editor" aria-label="Evidence editor">
        <div className="candidate-editor-heading">
          <div><p>{editor.mode === 'edit' ? 'Edit evidence' : 'New evidence'}</p><h2>{item?.title || 'Evidence item'}</h2></div>
          <button type="button" onClick={onClose}>Close</button>
        </div>
        <form onSubmit={submit}>
          <label>Type<select value={form.type} onChange={(event) => updateField('type', event.target.value)}>{EVIDENCE_TYPES.map(([type, label]) => <option value={type} key={type}>{label}</option>)}</select></label>
          <label>Title<input value={form.title} onChange={(event) => updateField('title', event.target.value)} required /></label>
          <label>Organization/context<input value={form.organization} onChange={(event) => updateField('organization', event.target.value)} /></label>
          <label>Location<input value={form.location} onChange={(event) => updateField('location', event.target.value)} /></label>
          <div className="candidate-editor-grid"><label>Start<input value={form.start_date} onChange={(event) => updateField('start_date', event.target.value)} /></label><label>End<input value={form.end_date} disabled={form.is_current} onChange={(event) => updateField('end_date', event.target.value)} /></label></div>
          <label className="candidate-checkbox"><input type="checkbox" checked={form.is_current} onChange={(event) => updateField('is_current', event.target.checked)} />Current</label>
          <label>Description<textarea rows="5" value={form.description} onChange={(event) => updateField('description', event.target.value)} /></label>
          <label>Skills/tags<input value={form.skills} onChange={(event) => updateField('skills', event.target.value)} placeholder="Python, SIEM, Linux" /></label>
          <label>URL<input value={form.url} onChange={(event) => updateField('url', event.target.value)} /></label>
          <label>Confidence<input type="number" min="0" max="1" step="0.1" value={form.confidence} onChange={(event) => updateField('confidence', event.target.value)} /></label>
          <div className="candidate-editor-actions"><button type="submit" disabled={isSaving || !form.title.trim()}>{isSaving ? 'Saving...' : 'Save evidence'}</button>{item && <button type="button" data-danger="true" disabled={isSaving} onClick={() => onDelete(item.id)}>Delete</button>}</div>
        </form>
      </aside>
    </div>
  )
}

function filterEvidence(items, query, reviewOnly) {
  const needle = query.trim().toLowerCase()
  return items.filter((item) => {
    if (reviewOnly && !isReviewCandidate(item)) return false
    if (!needle) return true
    return [item.title, item.organization, item.location, item.description, ...(item.skills || [])].filter(Boolean).join(' ').toLowerCase().includes(needle)
  })
}

function isReviewCandidate(item) {
  return Number(item.confidence ?? 1) < 0.75 || !item.source_document_id
}

function evidenceToForm(item, type) {
  return {
    type,
    title: item?.title || '',
    organization: item?.organization || '',
    location: item?.location || '',
    start_date: item?.start_date || '',
    end_date: item?.end_date || '',
    is_current: item?.is_current || false,
    description: item?.description || '',
    skills: item?.skills?.join(', ') || '',
    url: item?.url || '',
    confidence: item?.confidence ?? 1,
  }
}

function dateRange(item) {
  if (!item.start_date && !item.end_date && !item.is_current) return ''
  return `${item.start_date || ''}${item.end_date ? ` to ${item.end_date}` : item.is_current ? ' to present' : ''}`.trim()
}

function clamp01(value) {
  const number = Number(value)
  if (Number.isNaN(number)) return 1
  return Math.max(0, Math.min(1, number))
}

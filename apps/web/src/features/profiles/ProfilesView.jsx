import { useEffect, useState } from 'react'
import {
  createCandidateEvidence,
  createTargetProfile,
  deleteCandidateEvidence,
  deleteTargetProfile,
  getCandidate,
  listCandidateDocuments,
  listCandidateEvidence,
  suggestTargetProfiles,
  updateCandidate,
  updateCandidateEvidence,
  updateTargetProfile,
  uploadCandidateDocument,
} from '../../api.js'
import { blankToNull, csvValues } from '../../lib/forms.js'
import { profileName } from '../../lib/profile.js'

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

export function ProfilesView({
  profiles,
  selectedProfileId,
  isCreating,
  error,
  onSelectProfile,
  onProfilesRefresh,
}) {
  const targetProfiles = profiles || []
  const selectedTargetProfile = targetProfiles.find((profile) => profile.id === selectedProfileId) || null
  const [candidate, setCandidate] = useState(null)
  const [documents, setDocuments] = useState([])
  const [evidence, setEvidence] = useState([])
  const [workspaceError, setWorkspaceError] = useState('')
  const [isLoadingWorkspace, setIsLoadingWorkspace] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [editingEvidence, setEditingEvidence] = useState({ type: null, id: null })
  const [targetDraft, setTargetDraft] = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [isSuggesting, setIsSuggesting] = useState(false)

  useEffect(() => {
    loadWorkspace()
  }, [])

  useEffect(() => {
    setTargetDraft(selectedTargetProfile ? targetProfileToDraft(selectedTargetProfile) : blankTargetProfile())
  }, [selectedTargetProfile?.id])

  async function loadWorkspace() {
    setIsLoadingWorkspace(true)
    setWorkspaceError('')
    try {
      const [candidateResult, documentResult, evidenceResult] = await Promise.allSettled([
        getCandidate(),
        listCandidateDocuments({ limit: 100 }),
        listCandidateEvidence({ limit: 1000 }),
      ])
      if (candidateResult.status === 'fulfilled') setCandidate(candidateResult.value)
      if (documentResult.status === 'fulfilled') setDocuments(documentResult.value)
      if (evidenceResult.status === 'fulfilled') setEvidence(evidenceResult.value)
      const rejected = [candidateResult, documentResult, evidenceResult].find((result) => result.status === 'rejected')
      if (rejected && rejected.reason?.message !== 'Candidate not found') setWorkspaceError(rejected.reason.message)
    } finally {
      setIsLoadingWorkspace(false)
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
      await loadWorkspace()
      await onProfilesRefresh?.()
    })
  }

  async function saveEvidence(payload, evidenceId = null) {
    await runSaving(async () => {
      if (evidenceId) {
        await updateCandidateEvidence(evidenceId, payload)
      } else {
        await createCandidateEvidence(payload)
      }
      setEvidence(await listCandidateEvidence({ limit: 1000 }))
      setEditingEvidence({ type: null, id: null })
    })
  }

  async function removeEvidence(evidenceId) {
    await runSaving(async () => {
      await deleteCandidateEvidence(evidenceId)
      setEvidence(await listCandidateEvidence({ limit: 1000 }))
      await onProfilesRefresh?.()
    })
  }

  async function saveTargetProfile(payload) {
    await runSaving(async () => {
      const saved = selectedTargetProfile
        ? await updateTargetProfile(selectedTargetProfile.id, payload)
        : await createTargetProfile(payload)
      await onProfilesRefresh?.()
      onSelectProfile?.(saved.id)
    })
  }

  async function removeTargetProfile() {
    if (!selectedTargetProfile) return
    await runSaving(async () => {
      await deleteTargetProfile(selectedTargetProfile.id)
      await onProfilesRefresh?.()
      onSelectProfile?.(null)
    })
  }

  async function requestSuggestions() {
    setIsSuggesting(true)
    setWorkspaceError('')
    try {
      setSuggestions(await suggestTargetProfiles({ count: 3 }))
    } catch (error) {
      setWorkspaceError(error.message)
    } finally {
      setIsSuggesting(false)
    }
  }

  async function saveSuggestion(suggestion) {
    await runSaving(async () => {
      const saved = await createTargetProfile(suggestion)
      setSuggestions((current) => current.filter((item) => item !== suggestion))
      await onProfilesRefresh?.()
      onSelectProfile?.(saved.id)
    })
  }

  async function runSaving(action) {
    setIsSaving(true)
    setWorkspaceError('')
    try {
      await action()
    } catch (error) {
      setWorkspaceError(error.message)
    } finally {
      setIsSaving(false)
    }
  }

  const combinedError = workspaceError || error

  return (
    <section className="profiles-view" aria-label="Candidate workspace">
      <header className="profiles-header">
        <div>
          <p>Candidate</p>
          <h1>{candidate?.display_name || 'Candidate knowledge'}</h1>
          <span>Maintain one durable evidence base, then shape job-specific target profiles for matching.</span>
        </div>
      </header>

      {combinedError && (
        <div className="profiles-state warning-state" role="alert">
          <strong>Candidate action failed.</strong>
          <span>{combinedError}</span>
        </div>
      )}

      <div className="profiles-layout candidate-layout">
        <div className="profiles-column">
          <CandidateSummary candidate={candidate} isSaving={isSaving} onSave={saveCandidate} />
          <DocumentPanel documents={documents} isLoading={isLoadingWorkspace} isSaving={isSaving} onUpload={uploadDocument} />
          <EvidencePanel
            evidence={evidence}
            editing={editingEvidence}
            isSaving={isSaving}
            onEdit={setEditingEvidence}
            onSave={saveEvidence}
            onDelete={removeEvidence}
          />
        </div>

        <aside className="candidate-target-panel">
          <TargetProfilePanel
            targetProfiles={targetProfiles}
            selectedTargetProfile={selectedTargetProfile}
            selectedProfileId={selectedProfileId}
            targetDraft={targetDraft || blankTargetProfile()}
            evidence={evidence}
            suggestions={suggestions}
            isSaving={isSaving || isCreating}
            isSuggesting={isSuggesting}
            onSelect={onSelectProfile}
            onDraftChange={setTargetDraft}
            onSave={saveTargetProfile}
            onDelete={removeTargetProfile}
            onSuggest={requestSuggestions}
            onSaveSuggestion={saveSuggestion}
          />
        </aside>
      </div>
    </section>
  )
}

function CandidateSummary({ candidate, isSaving, onSave }) {
  const [form, setForm] = useState(() => candidateToForm(candidate))

  useEffect(() => {
    setForm(candidateToForm(candidate))
  }, [candidate?.id])

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
    <form className="profile-form" onSubmit={submit}>
      <div><p>Identity</p><h2>One candidate record</h2></div>
      <div className="profile-form-grid">
        <label>Name<input value={form.display_name} onChange={(event) => updateField('display_name', event.target.value)} placeholder="Candidate name" /></label>
        <label>Headline<input value={form.headline} onChange={(event) => updateField('headline', event.target.value)} placeholder="Backend engineer, AI product builder" /></label>
      </div>
      <label>Summary<textarea value={form.summary} onChange={(event) => updateField('summary', event.target.value)} rows="4" placeholder="Short durable candidate summary." /></label>
      <button type="submit" disabled={isSaving}>{isSaving ? 'Saving...' : 'Save candidate'}</button>
    </form>
  )
}

function DocumentPanel({ documents, isLoading, isSaving, onUpload }) {
  function handleFileChange(event) {
    const file = event.target.files?.[0]
    if (file) onUpload(file)
    event.target.value = ''
  }

  return (
    <section className="profile-cv-handling" aria-label="Candidate documents">
      <div>
        <p>Documents</p>
        <h2>{documents.length ? `${documents.length} source document${documents.length === 1 ? '' : 's'}` : 'No documents yet'}</h2>
      </div>
      <div className="profile-cv-copy">
        <span>{isLoading ? 'Loading candidate source documents...' : 'Upload a CV to extract candidate evidence and keep the original text available for review.'}</span>
        {documents[0] && <small>Latest: {documents[0].filename || documents[0].source}</small>}
        <label className="profile-cv-upload-action">
          <input type="file" accept="application/pdf,.pdf" disabled={isSaving} onChange={handleFileChange} />
          <span>{isSaving ? 'Uploading...' : 'Upload CV'}</span>
        </label>
      </div>
    </section>
  )
}

function EvidencePanel({ evidence, editing, isSaving, onEdit, onSave, onDelete }) {
  return (
    <section className="profile-enrichment" aria-label="Candidate evidence">
      <div className="profile-enrichment-heading">
        <p>Evidence</p>
        <h2>Proof library</h2>
        <span>Each item is indexed for matching and can be weighted inside target profiles.</span>
      </div>
      <div className="profile-enrichment-sections">
        {EVIDENCE_TYPES.map(([type, label]) => {
          const items = evidence.filter((item) => item.type === type)
          const isAdding = editing.type === type && editing.id === 'new'
          return (
            <section className="profile-enrichment-section" key={type}>
              <div className="profile-enrichment-section-title">
                <h3>{label}</h3>
                <div>
                  <span>{items.length}</span>
                  <button type="button" onClick={() => onEdit(isAdding ? { type: null, id: null } : { type, id: 'new' })}>{isAdding ? 'Close' : 'Add'}</button>
                </div>
              </div>
              {isAdding && <EvidenceForm type={type} isSaving={isSaving} onSubmit={(payload) => onSave(payload)} />}
              <div className="profile-enrichment-list">
                {items.length === 0 && <p className="profile-enrichment-empty">No {label.toLowerCase()} evidence yet.</p>}
                {items.map((item) => (
                  editing.type === type && editing.id === item.id ? (
                    <EvidenceForm key={item.id} item={item} type={type} isSaving={isSaving} submitLabel="Save evidence" onCancel={() => onEdit({ type: null, id: null })} onSubmit={(payload) => onSave(payload, item.id)} />
                  ) : (
                    <EvidenceItem key={item.id} item={item} isSaving={isSaving} onEdit={() => onEdit({ type, id: item.id })} onDelete={() => onDelete(item.id)} />
                  )
                ))}
              </div>
            </section>
          )
        })}
      </div>
    </section>
  )
}

function EvidenceItem({ item, isSaving, onEdit, onDelete }) {
  return (
    <div className="profile-enrichment-item">
      <div>
        <strong>{item.title}</strong>
        <span>{[item.organization, item.location, item.start_date, item.end_date || (item.is_current ? 'present' : null)].filter(Boolean).join(' / ')}</span>
        {item.description && <p>{item.description}</p>}
        {item.skills?.length > 0 && <small>{item.skills.join(', ')}</small>}
      </div>
      <div className="profile-enrichment-actions">
        <button type="button" disabled={isSaving} onClick={onEdit}>Edit</button>
        <button type="button" disabled={isSaving} onClick={onDelete}>Delete</button>
      </div>
    </div>
  )
}

function EvidenceForm({ item, type, isSaving, submitLabel = 'Add evidence', onSubmit, onCancel }) {
  const [form, setForm] = useState(() => evidenceToForm(item, type))

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    await onSubmit({
      type,
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
      confidence: Number(form.confidence) || 1,
    })
    if (!item) setForm(evidenceToForm(null, type))
  }

  return (
    <form className="profile-enrichment-form" onSubmit={submit}>
      <div className="profile-form-grid">
        <label>Title<input value={form.title} onChange={(event) => updateField('title', event.target.value)} placeholder="Evidence title" required /></label>
        <label>Organization<input value={form.organization} onChange={(event) => updateField('organization', event.target.value)} placeholder="Company, school, project" /></label>
        <label>Location<input value={form.location} onChange={(event) => updateField('location', event.target.value)} placeholder="Remote, London" /></label>
        <label>Start<input value={form.start_date} onChange={(event) => updateField('start_date', event.target.value)} placeholder="2022" /></label>
        <label>End<input value={form.end_date} onChange={(event) => updateField('end_date', event.target.value)} placeholder="2024" disabled={form.is_current} /></label>
        <label>Skills<input value={form.skills} onChange={(event) => updateField('skills', event.target.value)} placeholder="Python, Postgres" /></label>
        <label>URL<input value={form.url} onChange={(event) => updateField('url', event.target.value)} placeholder="https://..." /></label>
        <label>Confidence<input type="number" min="0" max="1" step="0.1" value={form.confidence} onChange={(event) => updateField('confidence', event.target.value)} /></label>
      </div>
      <label className="profile-checkbox-row"><input type="checkbox" checked={form.is_current} onChange={(event) => updateField('is_current', event.target.checked)} />Current</label>
      <label>Description<textarea value={form.description} onChange={(event) => updateField('description', event.target.value)} rows="3" placeholder="Responsibilities, outcomes, proof points." /></label>
      <div className="profile-enrichment-form-actions">
        <button type="submit" disabled={isSaving || !form.title.trim()}>{isSaving ? 'Saving...' : submitLabel}</button>
        {onCancel && <button type="button" disabled={isSaving} onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  )
}

function TargetProfilePanel({
  targetProfiles,
  selectedTargetProfile,
  selectedProfileId,
  targetDraft,
  evidence,
  suggestions,
  isSaving,
  isSuggesting,
  onSelect,
  onDraftChange,
  onSave,
  onDelete,
  onSuggest,
  onSaveSuggestion,
}) {
  return (
    <div className="target-profile-card">
      <div className="profile-enrichment-heading">
        <p>Target profiles</p>
        <h2>Job-search personas</h2>
        <span>Select one for chat and matching, or create another from candidate evidence.</span>
      </div>

      <div className="target-profile-list">
        {targetProfiles.map((profile) => (
          <button key={profile.id} type="button" data-active={profile.id === selectedProfileId} onClick={() => onSelect(profile.id)}>
            <strong>{profileName(profile)}</strong>
            <span>{profile.target_roles?.join(', ') || 'General target'}</span>
          </button>
        ))}
        {!targetProfiles.length && <p className="profile-enrichment-empty">No target profiles yet.</p>}
      </div>

      <TargetProfileForm
        key={selectedTargetProfile?.id || 'new-target'}
        draft={targetDraft}
        evidence={evidence}
        isSaving={isSaving}
        submitLabel={selectedTargetProfile ? 'Save target profile' : 'Create target profile'}
        onChange={onDraftChange}
        onSubmit={onSave}
      />

      {selectedTargetProfile && <button className="profile-text-action" type="button" disabled={isSaving} onClick={onDelete}>Delete selected target profile</button>}

      <div className="target-suggestion-panel">
        <button type="button" disabled={isSuggesting || isSaving} onClick={onSuggest}>{isSuggesting ? 'Suggesting...' : 'Suggest target profiles'}</button>
        {suggestions.map((suggestion, index) => (
          <article key={`${suggestion.name}-${index}`}>
            <strong>{suggestion.name}</strong>
            <span>{suggestion.summary || suggestion.target_roles?.join(', ') || 'Suggested draft'}</span>
            <button type="button" disabled={isSaving} onClick={() => onSaveSuggestion(suggestion)}>Save draft</button>
          </article>
        ))}
      </div>
    </div>
  )
}

function TargetProfileForm({ draft, evidence, isSaving, submitLabel, onChange, onSubmit }) {
  function updateField(field, value) {
    onChange({ ...draft, [field]: value })
  }

  function updateEvidence(evidenceId, patch) {
    const current = draft.evidence.find((item) => item.evidence_id === evidenceId)
    const next = current ? { ...current, ...patch } : { evidence_id: evidenceId, weight: 0.8, note: null, ...patch }
    onChange({ ...draft, evidence: [...draft.evidence.filter((item) => item.evidence_id !== evidenceId), next] })
  }

  function toggleEvidence(evidenceId, checked) {
    if (checked) updateEvidence(evidenceId, {})
    else onChange({ ...draft, evidence: draft.evidence.filter((item) => item.evidence_id !== evidenceId) })
  }

  function submit(event) {
    event.preventDefault()
    onSubmit(targetDraftToPayload(draft))
  }

  return (
    <form className="profile-form target-profile-form" onSubmit={submit}>
      <label>Name<input value={draft.name} onChange={(event) => updateField('name', event.target.value)} placeholder="Senior backend in fintech" required /></label>
      <label>Summary<textarea value={draft.summary} onChange={(event) => updateField('summary', event.target.value)} rows="3" placeholder="What this target profile optimizes for." /></label>
      <div className="profile-form-grid">
        <label>Roles<input value={draft.target_roles} onChange={(event) => updateField('target_roles', event.target.value)} placeholder="Backend engineer, platform engineer" /></label>
        <label>Locations<input value={draft.target_locations} onChange={(event) => updateField('target_locations', event.target.value)} placeholder="London, Remote" /></label>
        <label>Contracts<input value={draft.preferred_contract_types} onChange={(event) => updateField('preferred_contract_types', event.target.value)} placeholder="full-time, contract" /></label>
        <label>Seniority<input value={draft.seniority} onChange={(event) => updateField('seniority', event.target.value)} placeholder="senior" /></label>
        <label>Remote<input value={draft.remote_preference} onChange={(event) => updateField('remote_preference', event.target.value)} placeholder="hybrid" /></label>
        <label>Must-have<input value={draft.must_have_keywords} onChange={(event) => updateField('must_have_keywords', event.target.value)} placeholder="Python, Postgres" /></label>
        <label>Nice-to-have<input value={draft.nice_to_have_keywords} onChange={(event) => updateField('nice_to_have_keywords', event.target.value)} placeholder="LangGraph, React" /></label>
        <label>Avoid<input value={draft.avoid_keywords} onChange={(event) => updateField('avoid_keywords', event.target.value)} placeholder="unpaid, commission" /></label>
      </div>
      <label>Instructions<textarea value={draft.instructions} onChange={(event) => updateField('instructions', event.target.value)} rows="2" placeholder="Extra matching instructions." /></label>

      <div className="target-evidence-editor">
        <strong>Evidence weights</strong>
        {evidence.length === 0 && <p className="profile-enrichment-empty">Add evidence before weighting it for this target profile.</p>}
        {evidence.map((item) => {
          const link = draft.evidence.find((entry) => entry.evidence_id === item.id)
          return (
            <label className="target-evidence-row" key={item.id}>
              <input type="checkbox" checked={Boolean(link)} onChange={(event) => toggleEvidence(item.id, event.target.checked)} />
              <span>{item.title}</span>
              <input type="number" min="0" max="1" step="0.1" disabled={!link} value={link?.weight ?? 0.8} onChange={(event) => updateEvidence(item.id, { weight: clampWeight(event.target.value) })} />
            </label>
          )
        })}
      </div>

      <button type="submit" disabled={isSaving || !draft.name.trim()}>{isSaving ? 'Saving...' : submitLabel}</button>
    </form>
  )
}

function candidateToForm(candidate) {
  return {
    display_name: candidate?.display_name || '',
    headline: candidate?.headline || '',
    summary: candidate?.summary || '',
  }
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

function blankTargetProfile() {
  return {
    name: '',
    summary: '',
    target_roles: '',
    target_locations: '',
    preferred_contract_types: '',
    seniority: '',
    remote_preference: '',
    must_have_keywords: '',
    nice_to_have_keywords: '',
    avoid_keywords: '',
    instructions: '',
    evidence: [],
  }
}

function targetProfileToDraft(profile) {
  return {
    name: profile.name || '',
    summary: profile.summary || '',
    target_roles: (profile.target_roles || []).join(', '),
    target_locations: (profile.target_locations || []).join(', '),
    preferred_contract_types: (profile.preferred_contract_types || []).join(', '),
    seniority: profile.seniority || '',
    remote_preference: profile.remote_preference || '',
    must_have_keywords: (profile.must_have_keywords || []).join(', '),
    nice_to_have_keywords: (profile.nice_to_have_keywords || []).join(', '),
    avoid_keywords: (profile.avoid_keywords || []).join(', '),
    instructions: profile.instructions || '',
    evidence: (profile.evidence || []).map((item) => ({
      evidence_id: item.evidence_id,
      weight: item.weight,
      note: item.note || null,
    })),
  }
}

function targetDraftToPayload(draft) {
  return {
    name: draft.name.trim(),
    summary: blankToNull(draft.summary),
    target_roles: csvValues(draft.target_roles),
    target_locations: csvValues(draft.target_locations),
    preferred_contract_types: csvValues(draft.preferred_contract_types),
    seniority: blankToNull(draft.seniority),
    remote_preference: blankToNull(draft.remote_preference),
    must_have_keywords: csvValues(draft.must_have_keywords),
    nice_to_have_keywords: csvValues(draft.nice_to_have_keywords),
    avoid_keywords: csvValues(draft.avoid_keywords),
    instructions: blankToNull(draft.instructions),
    evidence: draft.evidence.map((item) => ({
      evidence_id: item.evidence_id,
      weight: clampWeight(item.weight),
      note: blankToNull(item.note),
    })),
  }
}

function clampWeight(value) {
  const number = Number(value)
  if (Number.isNaN(number)) return 0.8
  return Math.max(0, Math.min(1, number))
}

import { useEffect, useState } from 'react'
import {
  createTargetProfile,
  deleteTargetProfile,
  listCandidateEvidence,
  suggestTargetProfiles,
  updateTargetProfile,
} from '../../api.js'
import { blankToNull, csvValues } from '../../lib/forms.js'
import { profileName } from '../../lib/profile.js'

export function TargetProfilesView({ targetProfiles, selectedTargetProfileId, isLoading, error, onSelectTargetProfile, onRefreshTargetProfiles }) {
  const selectedTargetProfile = targetProfiles.find((profile) => profile.id === selectedTargetProfileId) || null
  const [candidateEvidence, setCandidateEvidence] = useState([])
  const [draft, setDraft] = useState(() => targetProfileToDraft(selectedTargetProfile))
  const [suggestions, setSuggestions] = useState([])
  const [workspaceError, setWorkspaceError] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isSuggesting, setIsSuggesting] = useState(false)

  useEffect(() => {
    loadEvidence()
  }, [])

  useEffect(() => {
    setDraft(targetProfileToDraft(selectedTargetProfile))
  }, [selectedTargetProfile?.id])

  async function loadEvidence() {
    setWorkspaceError('')
    try {
      setCandidateEvidence(await listCandidateEvidence({ limit: 1000 }))
    } catch (err) {
      setWorkspaceError(err.message)
    }
  }

  async function saveTargetProfile(payload) {
    await runSaving(async () => {
      const saved = selectedTargetProfile
        ? await updateTargetProfile(selectedTargetProfile.id, payload)
        : await createTargetProfile(payload)
      await onRefreshTargetProfiles()
      onSelectTargetProfile(saved.id)
    })
  }

  async function removeTargetProfile() {
    if (!selectedTargetProfile) return
    await runSaving(async () => {
      await deleteTargetProfile(selectedTargetProfile.id)
      await onRefreshTargetProfiles()
      onSelectTargetProfile(null)
    })
  }

  async function requestSuggestions() {
    setIsSuggesting(true)
    setWorkspaceError('')
    try {
      setSuggestions(await suggestTargetProfiles({ count: 3 }))
    } catch (err) {
      setWorkspaceError(err.message)
    } finally {
      setIsSuggesting(false)
    }
  }

  async function saveSuggestion(suggestion) {
    await runSaving(async () => {
      const saved = await createTargetProfile(suggestion)
      setSuggestions((current) => current.filter((item) => item !== suggestion))
      await onRefreshTargetProfiles()
      onSelectTargetProfile(saved.id)
    })
  }

  async function runSaving(action) {
    setIsSaving(true)
    setWorkspaceError('')
    try {
      await action()
    } catch (err) {
      setWorkspaceError(err.message)
    } finally {
      setIsSaving(false)
    }
  }

  const combinedError = workspaceError || error

  return (
    <section className="target-profiles-view" aria-label="Target profiles workspace">
      <header className="target-profiles-hero">
        <div>
          <p>Target profiles</p>
          <h1>Shape the search persona.</h1>
          <span>Select candidate evidence, tune weights, and define keywords for each job-search direction.</span>
        </div>
        <button type="button" onClick={() => { onSelectTargetProfile(null); setDraft(blankTargetProfile()) }}>New target profile</button>
      </header>

      {combinedError && <div className="candidate-alert warning-state" role="alert"><strong>Target profile action failed.</strong><span>{combinedError}</span></div>}

      <div className="target-profiles-layout">
        <aside className="target-profile-index">
          <div className="target-index-heading"><strong>{isLoading ? 'Refreshing...' : 'Saved personas'}</strong><span>{targetProfiles.length}</span></div>
          {targetProfiles.length === 0 && <p>No target profiles yet. Create one manually or ask Scout to suggest drafts.</p>}
          {targetProfiles.map((profile) => (
            <button type="button" key={profile.id} data-active={profile.id === selectedTargetProfileId} onClick={() => onSelectTargetProfile(profile.id)}>
              <strong>{profileName(profile)}</strong>
              <span>{profile.target_roles?.join(', ') || profile.summary || 'General target'}</span>
            </button>
          ))}
          <div className="target-ai-box">
            <strong>AI drafts</strong>
            <p>Generate unsaved target profile drafts from candidate evidence.</p>
            <button type="button" disabled={isSuggesting || isSaving} onClick={requestSuggestions}>{isSuggesting ? 'Suggesting...' : 'Suggest profiles'}</button>
          </div>
        </aside>

        <div className="target-profile-editor-shell">
          <TargetProfileForm
            draft={draft}
            evidence={candidateEvidence}
            isSaving={isSaving}
            selectedTargetProfile={selectedTargetProfile}
            onChange={setDraft}
            onSubmit={saveTargetProfile}
            onDelete={removeTargetProfile}
          />
          {suggestions.length > 0 && <SuggestionStrip suggestions={suggestions} isSaving={isSaving} onSave={saveSuggestion} />}
        </div>
      </div>
    </section>
  )
}

function TargetProfileForm({ draft, evidence, isSaving, selectedTargetProfile, onChange, onSubmit, onDelete }) {
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
    <form className="target-profile-editor" onSubmit={submit}>
      <div className="target-editor-heading">
        <div><p>{selectedTargetProfile ? 'Edit persona' : 'New persona'}</p><h2>{draft.name || 'Target profile'}</h2></div>
        {selectedTargetProfile && <button type="button" data-danger="true" disabled={isSaving} onClick={onDelete}>Delete</button>}
      </div>

      <label>Name<input value={draft.name} onChange={(event) => updateField('name', event.target.value)} placeholder="Cybersecurity internship" required /></label>
      <label>Summary<textarea value={draft.summary} onChange={(event) => updateField('summary', event.target.value)} rows="3" placeholder="What this job-search persona optimizes for." /></label>
      <div className="target-editor-grid">
        <label>Roles<input value={draft.target_roles} onChange={(event) => updateField('target_roles', event.target.value)} placeholder="SOC analyst, security intern" /></label>
        <label>Locations<input value={draft.target_locations} onChange={(event) => updateField('target_locations', event.target.value)} placeholder="Luxembourg, remote" /></label>
        <label>Contracts<input value={draft.preferred_contract_types} onChange={(event) => updateField('preferred_contract_types', event.target.value)} placeholder="internship, full-time" /></label>
        <label>Seniority<input value={draft.seniority} onChange={(event) => updateField('seniority', event.target.value)} placeholder="student, junior, senior" /></label>
        <label>Remote preference<input value={draft.remote_preference} onChange={(event) => updateField('remote_preference', event.target.value)} placeholder="hybrid" /></label>
        <label>Must-have keywords<input value={draft.must_have_keywords} onChange={(event) => updateField('must_have_keywords', event.target.value)} placeholder="Python, Linux, SIEM" /></label>
        <label>Nice-to-have keywords<input value={draft.nice_to_have_keywords} onChange={(event) => updateField('nice_to_have_keywords', event.target.value)} placeholder="SOC, Docker" /></label>
        <label>Avoid keywords<input value={draft.avoid_keywords} onChange={(event) => updateField('avoid_keywords', event.target.value)} placeholder="commission, unpaid" /></label>
      </div>
      <label>Instructions<textarea value={draft.instructions} onChange={(event) => updateField('instructions', event.target.value)} rows="2" placeholder="Extra ranking instructions." /></label>

      <div className="target-evidence-picker">
        <div className="target-editor-heading compact"><div><p>Evidence weights</p><h2>Pick the proof</h2></div><span>{draft.evidence.length} selected</span></div>
        {evidence.length === 0 && <p>No candidate evidence yet. Add base knowledge in Candidate first.</p>}
        <div className="target-evidence-list">
          {evidence.map((item) => {
            const link = draft.evidence.find((entry) => entry.evidence_id === item.id)
            return (
              <label className="target-evidence-card" data-selected={Boolean(link)} key={item.id}>
                <input type="checkbox" checked={Boolean(link)} onChange={(event) => toggleEvidence(item.id, event.target.checked)} />
                <span><strong>{item.title}</strong><small>{[item.type, item.organization, item.skills?.slice(0, 3).join(', ')].filter(Boolean).join(' / ')}</small></span>
                <input type="number" min="0" max="1" step="0.1" disabled={!link} value={link?.weight ?? 0.8} onChange={(event) => updateEvidence(item.id, { weight: clampWeight(event.target.value) })} />
              </label>
            )
          })}
        </div>
      </div>

      <button type="submit" disabled={isSaving || !draft.name.trim()}>{isSaving ? 'Saving...' : selectedTargetProfile ? 'Save target profile' : 'Create target profile'}</button>
    </form>
  )
}

function SuggestionStrip({ suggestions, isSaving, onSave }) {
  return (
    <section className="target-suggestions">
      <div className="target-editor-heading compact"><div><p>Suggested drafts</p><h2>Review before saving</h2></div></div>
      <div className="target-suggestion-grid">
        {suggestions.map((suggestion, index) => (
          <article key={`${suggestion.name}-${index}`}>
            <strong>{suggestion.name}</strong>
            <span>{suggestion.summary || suggestion.target_roles?.join(', ') || 'Suggested target profile'}</span>
            <button type="button" disabled={isSaving} onClick={() => onSave(suggestion)}>Save draft</button>
          </article>
        ))}
      </div>
    </section>
  )
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
  if (!profile) return blankTargetProfile()
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
    evidence: (profile.evidence || []).map((item) => ({ evidence_id: item.evidence_id, weight: item.weight, note: item.note || null })),
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
    evidence: draft.evidence.map((item) => ({ evidence_id: item.evidence_id, weight: clampWeight(item.weight), note: blankToNull(item.note) })),
  }
}

function clampWeight(value) {
  const number = Number(value)
  if (Number.isNaN(number)) return 0.8
  return Math.max(0, Math.min(1, number))
}

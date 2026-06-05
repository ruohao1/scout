import { useState } from 'react'
import { blankToNull, csvValues } from '../../lib/forms.js'
import { profileName } from '../../lib/profile.js'

export function ProfilesView({ profiles, selectedProfileId, isLoading, isCreating, isUploading, error, onRefresh, onSelectProfile, onCreateProfile, onUploadProfile }) {
  const selectedProfile = profiles.find((profile) => profile.id === selectedProfileId) || null

  return (
    <section className="profiles-view" aria-label="Candidate profiles">
      <header className="profiles-header">
        <div>
          <p>Profiles</p>
          <h1>Candidate context</h1>
          <span>{selectedProfile ? `Matching is using ${profileName(selectedProfile)}.` : 'Create or select a profile before asking Scout to rank jobs.'}</span>
        </div>
        <button type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </header>

      {error && (
        <div className="profiles-state warning-state" role="alert">
          <strong>Profile action failed.</strong>
          <span>{error}</span>
        </div>
      )}

      <div className="profiles-layout">
        <div className="profiles-column">
          {selectedProfile ? (
            <ProfileSummary profile={selectedProfile} />
          ) : (
            <div className="profiles-state">
              <strong>No profile selected.</strong>
              <span>Create a manual profile or select one from the list.</span>
            </div>
          )}

          <ProfileUploadForm isUploading={isUploading} onUploadProfile={onUploadProfile} />
          <ProfileForm isCreating={isCreating} onCreateProfile={onCreateProfile} />
        </div>

        <div className="profiles-list-card">
          <div className="profiles-list-header">
            <strong>Saved profiles</strong>
            <span>{profiles.length}</span>
          </div>

          {isLoading && !profiles.length && (
            <div className="profiles-state compact">
              <strong>Loading profiles...</strong>
              <span>Scout is asking the API for candidate profiles.</span>
            </div>
          )}

          {!isLoading && profiles.length === 0 && (
            <div className="profiles-state compact">
              <strong>No saved profiles yet.</strong>
              <span>Use the form to create the first candidate context.</span>
            </div>
          )}

          <div className="profiles-list">
            {profiles.map((profile) => (
              <button type="button" key={profile.id} className="profile-row" data-active={profile.id === selectedProfileId} onClick={() => onSelectProfile(profile.id)}>
                <span>{profileName(profile)}</span>
                <small>{profile.target_roles?.join(', ') || profile.seniority || 'General candidate'}</small>
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

function ProfileUploadForm({ isUploading, onUploadProfile }) {
  const [form, setForm] = useState({
    file: null,
    name: '',
    target_roles: '',
    target_locations: '',
    skills: '',
    seniority: '',
    preferred_contract_types: '',
    remote_preference: '',
    extract_profile: true,
  })

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function appendIfPresent(formData, field, value) {
    const trimmed = value.trim()
    if (trimmed) {
      formData.append(field, trimmed)
    }
  }

  function submit(event) {
    event.preventDefault()
    if (!form.file) return

    const formData = new FormData()
    formData.append('file', form.file)
    formData.append('extract_profile', String(form.extract_profile))
    formData.append('model', 'gpt-5.5')
    appendIfPresent(formData, 'name', form.name)
    appendIfPresent(formData, 'target_roles', form.target_roles)
    appendIfPresent(formData, 'target_locations', form.target_locations)
    appendIfPresent(formData, 'skills', form.skills)
    appendIfPresent(formData, 'seniority', form.seniority)
    appendIfPresent(formData, 'preferred_contract_types', form.preferred_contract_types)
    appendIfPresent(formData, 'remote_preference', form.remote_preference)

    onUploadProfile(formData)
  }

  return (
    <form className="profile-upload-form" onSubmit={submit}>
      <div>
        <p>Upload CV</p>
        <h2>Extract candidate context</h2>
        <span>Upload a CV up to 5 MB. Optional fields override extracted values.</span>
      </div>

      <label className="profile-file-input">
        CV file
        <input type="file" accept=".pdf,application/pdf" required onChange={(event) => updateField('file', event.target.files?.[0] || null)} />
        <small>{form.file ? `${form.file.name} (${Math.ceil(form.file.size / 1024)} KB)` : 'PDF only, up to 5 MB.'}</small>
      </label>

      <label className="profile-checkbox-row">
        <input type="checkbox" checked={form.extract_profile} onChange={(event) => updateField('extract_profile', event.target.checked)} />
        Extract profile fields with the configured model
      </label>

      <div className="profile-form-grid">
        <label>Name<input value={form.name} onChange={(event) => updateField('name', event.target.value)} placeholder="Optional display name" /></label>
        <label>Target roles<input value={form.target_roles} onChange={(event) => updateField('target_roles', event.target.value)} placeholder="Backend, ML engineer" /></label>
        <label>Locations<input value={form.target_locations} onChange={(event) => updateField('target_locations', event.target.value)} placeholder="Paris, Berlin" /></label>
        <label>Skills<input value={form.skills} onChange={(event) => updateField('skills', event.target.value)} placeholder="Python, FastAPI, SQL" /></label>
        <label>Seniority<input value={form.seniority} onChange={(event) => updateField('seniority', event.target.value)} placeholder="senior" /></label>
        <label>Remote preference<input value={form.remote_preference} onChange={(event) => updateField('remote_preference', event.target.value)} placeholder="hybrid" /></label>
      </div>

      <label>Contracts<input value={form.preferred_contract_types} onChange={(event) => updateField('preferred_contract_types', event.target.value)} placeholder="full-time, contract" /></label>

      <button type="submit" disabled={isUploading || !form.file}>
        {isUploading ? 'Uploading...' : 'Upload and select'}
      </button>
    </form>
  )
}

function ProfileSummary({ profile }) {
  return (
    <article className="profile-summary">
      <p>Selected profile</p>
      <h2>{profileName(profile)}</h2>
      <span>{profile.cv_text}</span>
      <ProfileChipGroup label="Roles" values={profile.target_roles} />
      <ProfileChipGroup label="Locations" values={profile.target_locations} />
      <ProfileChipGroup label="Skills" values={profile.skills} />
      <div className="profile-meta-grid">
        <div><small>Seniority</small><strong>{profile.seniority || 'Any'}</strong></div>
        <div><small>Contracts</small><strong>{profile.preferred_contract_types?.join(', ') || 'Any'}</strong></div>
        <div><small>Remote</small><strong>{profile.remote_preference || 'Any'}</strong></div>
      </div>
    </article>
  )
}

function ProfileChipGroup({ label, values = [] }) {
  if (!values.length) return null
  return (
    <div className="profile-chip-group">
      <small>{label}</small>
      <div className="tag-row">
        {values.map((value) => (
          <span key={value}>{value}</span>
        ))}
      </div>
    </div>
  )
}

function ProfileForm({ isCreating, onCreateProfile }) {
  const [form, setForm] = useState({
    name: '',
    cv_text: '',
    target_roles: '',
    target_locations: '',
    skills: '',
    seniority: '',
    preferred_contract_types: '',
    remote_preference: '',
  })

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function submit(event) {
    event.preventDefault()
    onCreateProfile({
      name: blankToNull(form.name),
      cv_text: form.cv_text.trim(),
      target_roles: csvValues(form.target_roles),
      target_locations: csvValues(form.target_locations),
      skills: csvValues(form.skills),
      seniority: blankToNull(form.seniority),
      preferred_contract_types: csvValues(form.preferred_contract_types),
      remote_preference: blankToNull(form.remote_preference),
    })
    setForm({ name: '', cv_text: '', target_roles: '', target_locations: '', skills: '', seniority: '', preferred_contract_types: '', remote_preference: '' })
  }

  return (
    <form className="profile-form" onSubmit={submit}>
      <div><p>Create profile</p><h2>Manual candidate brief</h2></div>
      <label>Name<input value={form.name} onChange={(event) => updateField('name', event.target.value)} placeholder="Candidate name" /></label>
      <label>CV text<textarea value={form.cv_text} onChange={(event) => updateField('cv_text', event.target.value)} placeholder="Paste a concise CV summary, experience, or goals." rows="5" required /></label>
      <div className="profile-form-grid">
        <label>Target roles<input value={form.target_roles} onChange={(event) => updateField('target_roles', event.target.value)} placeholder="Backend, ML engineer" /></label>
        <label>Locations<input value={form.target_locations} onChange={(event) => updateField('target_locations', event.target.value)} placeholder="Paris, Berlin" /></label>
        <label>Skills<input value={form.skills} onChange={(event) => updateField('skills', event.target.value)} placeholder="Python, FastAPI, SQL" /></label>
        <label>Seniority<input value={form.seniority} onChange={(event) => updateField('seniority', event.target.value)} placeholder="senior" /></label>
        <label>Contracts<input value={form.preferred_contract_types} onChange={(event) => updateField('preferred_contract_types', event.target.value)} placeholder="full-time, contract" /></label>
        <label>Remote preference<input value={form.remote_preference} onChange={(event) => updateField('remote_preference', event.target.value)} placeholder="hybrid" /></label>
      </div>
      <button type="submit" disabled={isCreating || !form.cv_text.trim()}>
        {isCreating ? 'Creating...' : 'Create and select'}
      </button>
    </form>
  )
}

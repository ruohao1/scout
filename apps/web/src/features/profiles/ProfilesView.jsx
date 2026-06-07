import { useEffect, useState } from 'react'
import { profileCvUrl } from '../../api.js'
import { blankToNull, csvValues } from '../../lib/forms.js'
import { profileName } from '../../lib/profile.js'

export function ProfilesView({
  profiles,
  selectedProfileId,
  isCreating,
  isAttachingCv,
  enrichment,
  isLoadingEnrichment,
  isSavingEnrichment,
  error,
  onCreateProfile,
  onUploadCvProfile,
  onAttachCv,
  onCreateExperience,
  onUpdateExperience,
  onDeleteExperience,
  onCreateProject,
  onUpdateProject,
  onDeleteProject,
  onCreateSkill,
  onUpdateSkill,
  onDeleteSkill,
}) {
  const selectedProfile = profiles.find((profile) => profile.id === selectedProfileId) || null
  const [editingSection, setEditingSection] = useState(null)
  const [isCreatingManual, setIsCreatingManual] = useState(false)

  useEffect(() => {
    setEditingSection(null)
    setIsCreatingManual(false)
  }, [selectedProfileId])

  function toggleEditingSection(section) {
    setEditingSection((current) => (current === section ? null : section))
  }

  return (
    <section className="profiles-view" aria-label="Candidate profiles">
      <header className="profiles-header">
        <div>
          <p>Profiles</p>
          <h1>{selectedProfile ? profileName(selectedProfile) : 'Candidate profile'}</h1>
          <span>{selectedProfile ? 'Profile context used for matching.' : 'Create or select a profile before asking Scout to rank jobs.'}</span>
        </div>
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
            <>
              <ProfileCvHandling profile={selectedProfile} enrichment={enrichment} isAttachingCv={isAttachingCv} onAttachCv={onAttachCv} />
              <ProfileEnrichmentOverview
                enrichment={enrichment}
                editingSection={editingSection}
                isLoading={isLoadingEnrichment}
                isSaving={isSavingEnrichment}
                onToggleSection={toggleEditingSection}
                onCreateExperience={onCreateExperience}
                onUpdateExperience={onUpdateExperience}
                onDeleteExperience={onDeleteExperience}
                onCreateProject={onCreateProject}
                onUpdateProject={onUpdateProject}
                onDeleteProject={onDeleteProject}
                onCreateSkill={onCreateSkill}
                onUpdateSkill={onUpdateSkill}
                onDeleteSkill={onDeleteSkill}
              />
            </>
          ) : (
            <div className="profiles-state">
              <strong>No profile selected.</strong>
              <span>{profiles.length ? 'Select a saved profile to review candidate context.' : 'Create or upload a profile to start matching jobs.'}</span>
              <div className="profile-empty-actions">
                <button type="button" onClick={() => setIsCreatingManual((current) => !current)}>{isCreatingManual ? 'Hide form' : 'Create profile'}</button>
                <CvUploadAction label={isCreating ? 'Uploading...' : 'Upload CV'} disabled={isCreating} onUpload={onUploadCvProfile} />
              </div>
            </div>
          )}

          {!selectedProfile && isCreatingManual && <ProfileForm isCreating={isCreating} onCreateProfile={onCreateProfile} />}
        </div>
      </div>
    </section>
  )
}

function ProfileCvHandling({ profile, enrichment, isAttachingCv, onAttachCv }) {
  const hasPdf = Boolean(profile.has_cv_file && profile.cv_filename)
  const evidenceSummary = parsedEvidenceSummary(enrichment)

  function handleFileChange(event) {
    const file = event.target.files?.[0]
    if (file) {
      onAttachCv(file)
    }
    event.target.value = ''
  }

  return (
    <section className="profile-cv-handling" aria-label="CV handling">
      <div>
        <p>CV</p>
        {hasPdf ? (
          <h2><a href={profileCvUrl(profile.id)} target="_blank" rel="noreferrer">{profile.cv_filename}</a></h2>
        ) : (
          <h2>No uploaded PDF attached</h2>
        )}
      </div>
      <div className="profile-cv-copy">
        <span>
          {hasPdf
            ? 'Open the uploaded PDF in a browser tab; raw CV text stays hidden from this view.'
            : 'Attach the candidate PDF or use structured evidence to refine matching context.'}
        </span>
        {evidenceSummary && <small>{evidenceSummary}</small>}
        <CvUploadAction label={isAttachingCv ? 'Attaching...' : hasPdf ? 'Replace PDF' : 'Upload PDF'} disabled={isAttachingCv} onUpload={onAttachCv} onChange={handleFileChange} />
      </div>
    </section>
  )
}

function CvUploadAction({ label, disabled, onUpload, onChange }) {
  function handleFileChange(event) {
    if (onChange) {
      onChange(event)
      return
    }
    const file = event.target.files?.[0]
    if (file) {
      onUpload(file)
    }
    event.target.value = ''
  }

  return (
    <label className="profile-cv-upload-action">
      <input type="file" accept="application/pdf,.pdf" onChange={handleFileChange} disabled={disabled} />
      <span>{label}</span>
    </label>
  )
}

function parsedEvidenceSummary(enrichment = { experiences: [], projects: [], enriched_skills: [] }) {
  const counts = [
    [enrichment.experiences?.length || 0, 'experience'],
    [enrichment.projects?.length || 0, 'project'],
    [enrichment.enriched_skills?.length || 0, 'skill'],
  ].filter(([count]) => count > 0)
  if (!counts.length) return ''
  return `Parsed ${counts.map(([count, label]) => `${count} ${label}${count === 1 ? '' : 's'}`).join(', ')}.`
}

function ProfileEnrichmentOverview({
  enrichment = { experiences: [], projects: [], enriched_skills: [] },
  editingSection,
  isLoading,
  isSaving,
  onToggleSection,
  onCreateExperience,
  onUpdateExperience,
  onDeleteExperience,
  onCreateProject,
  onUpdateProject,
  onDeleteProject,
  onCreateSkill,
  onUpdateSkill,
  onDeleteSkill,
}) {
  const [editing, setEditing] = useState({ type: null, id: null })

  useEffect(() => {
    setEditing({ type: null, id: null })
  }, [editingSection])

  function edit(type, id) {
    setEditing({ type, id })
  }

  function stopEditing() {
    setEditing({ type: null, id: null })
  }

  return (
    <section className="profile-enrichment" aria-label="Profile enrichment overview">
      {isLoading && <p className="profile-enrichment-empty">Loading CV evidence...</p>}

      <div className="profile-enrichment-sections">
        <EnrichmentSection title="Experience" count={enrichment.experiences?.length || 0} isEditing={editingSection === 'experience'} onToggle={() => onToggleSection('experience')}>
          {editingSection === 'experience' ? (
            <>
              <ExperienceForm isSaving={isSaving} onSubmit={onCreateExperience} />
              <ExperienceList items={enrichment.experiences || []} editing={editing} isSaving={isSaving} onEdit={edit} onCancel={stopEditing} onUpdate={onUpdateExperience} onDelete={onDeleteExperience} />
            </>
          ) : (
            <ReadOnlyExperienceList items={enrichment.experiences || []} />
          )}
        </EnrichmentSection>

        <EnrichmentSection title="Projects" count={enrichment.projects?.length || 0} isEditing={editingSection === 'projects'} onToggle={() => onToggleSection('projects')}>
          {editingSection === 'projects' ? (
            <>
              <ProjectForm isSaving={isSaving} onSubmit={onCreateProject} />
              <ProjectList items={enrichment.projects || []} editing={editing} isSaving={isSaving} onEdit={edit} onCancel={stopEditing} onUpdate={onUpdateProject} onDelete={onDeleteProject} />
            </>
          ) : (
            <ReadOnlyProjectList items={enrichment.projects || []} />
          )}
        </EnrichmentSection>

        <EnrichmentSection title="Skills" count={enrichment.enriched_skills?.length || 0} isEditing={editingSection === 'skills'} onToggle={() => onToggleSection('skills')}>
          {editingSection === 'skills' ? (
            <>
              <SkillForm isSaving={isSaving} onSubmit={onCreateSkill} />
              <SkillList items={enrichment.enriched_skills || []} editing={editing} isSaving={isSaving} onEdit={edit} onCancel={stopEditing} onUpdate={onUpdateSkill} onDelete={onDeleteSkill} />
            </>
          ) : (
            <ReadOnlySkillList items={enrichment.enriched_skills || []} />
          )}
        </EnrichmentSection>
      </div>
    </section>
  )
}

function ReadOnlyExperienceList({ items }) {
  if (!items.length) return <p className="profile-enrichment-empty">No experience added yet.</p>
  return (
    <div className="profile-enrichment-list">
      {items.map((item) => (
        <ExperienceItem item={item} key={item.id} />
      ))}
    </div>
  )
}

function ReadOnlyProjectList({ items }) {
  if (!items.length) return <p className="profile-enrichment-empty">No projects added yet.</p>
  return (
    <div className="profile-enrichment-list">
      {items.map((item) => (
        <ProjectItem item={item} key={item.id} />
      ))}
    </div>
  )
}

function ReadOnlySkillList({ items }) {
  const [isExpanded, setIsExpanded] = useState(false)
  if (!items.length) return <p className="profile-enrichment-empty">No extra skills added yet.</p>
  const visibleItems = isExpanded ? items : items.slice(0, 12)
  const hiddenCount = items.length - visibleItems.length
  return (
    <>
      <div className="profile-enrichment-list compact-list profile-skills-grid">
        {visibleItems.map((item) => (
          <SkillItem item={item} key={item.id} />
        ))}
      </div>
      {items.length > 12 && (
        <button className="profile-text-action" type="button" onClick={() => setIsExpanded((expanded) => !expanded)}>
          {isExpanded ? 'Show fewer skills' : `Show all ${items.length} skills${hiddenCount ? ` (${hiddenCount} more)` : ''}`}
        </button>
      )}
    </>
  )
}

function EnrichmentSection({ title, count, isEditing, onToggle, children }) {
  return (
    <section className="profile-enrichment-section">
      <div className="profile-enrichment-section-title">
        <h3>{title}</h3>
        <div>
          <span>{count}</span>
          <button type="button" onClick={onToggle}>{isEditing ? 'Done' : 'Edit'}</button>
        </div>
      </div>
      {children}
    </section>
  )
}

function ExperienceList({ items, editing, isSaving, onEdit, onCancel, onUpdate, onDelete }) {
  if (!items.length) return <p className="profile-enrichment-empty">No experience added yet.</p>
  return (
    <div className="profile-enrichment-list">
      {items.map((item) => (
        editing.type === 'experience' && editing.id === item.id ? (
          <div className="profile-enrichment-item" key={item.id}>
            <ExperienceForm initialValue={item} isSaving={isSaving} submitLabel="Save experience" onCancel={onCancel} onSubmit={async (payload) => { await onUpdate(item.id, payload); onCancel() }} />
          </div>
        ) : (
          <ExperienceItem item={item} key={item.id}>
            <InlineActions isSaving={isSaving} onEdit={() => onEdit('experience', item.id)} onDelete={() => onDelete(item.id)} />
          </ExperienceItem>
        )
      ))}
    </div>
  )
}

function ProjectList({ items, editing, isSaving, onEdit, onCancel, onUpdate, onDelete }) {
  if (!items.length) return <p className="profile-enrichment-empty">No projects added yet.</p>
  return (
    <div className="profile-enrichment-list">
      {items.map((item) => (
        editing.type === 'project' && editing.id === item.id ? (
          <div className="profile-enrichment-item" key={item.id}>
            <ProjectForm initialValue={item} isSaving={isSaving} submitLabel="Save project" onCancel={onCancel} onSubmit={async (payload) => { await onUpdate(item.id, payload); onCancel() }} />
          </div>
        ) : (
          <ProjectItem item={item} key={item.id}>
            <InlineActions isSaving={isSaving} onEdit={() => onEdit('project', item.id)} onDelete={() => onDelete(item.id)} />
          </ProjectItem>
        )
      ))}
    </div>
  )
}

function SkillList({ items, editing, isSaving, onEdit, onCancel, onUpdate, onDelete }) {
  const [isExpanded, setIsExpanded] = useState(false)
  if (!items.length) return <p className="profile-enrichment-empty">No extra skills added yet.</p>
  const visibleItems = isExpanded ? items : items.slice(0, 12)
  const hiddenCount = items.length - visibleItems.length
  return (
    <>
      <div className="profile-enrichment-list compact-list profile-skills-grid">
        {visibleItems.map((item) => (
          editing.type === 'skill' && editing.id === item.id ? (
            <div className="profile-enrichment-item" key={item.id}>
              <SkillForm initialValue={item} isSaving={isSaving} submitLabel="Save skill" onCancel={onCancel} onSubmit={async (payload) => { await onUpdate(item.id, payload); onCancel() }} />
            </div>
          ) : (
            <SkillItem item={item} key={item.id}>
              <InlineActions isSaving={isSaving} onEdit={() => onEdit('skill', item.id)} onDelete={() => onDelete(item.id)} />
            </SkillItem>
          )
        ))}
      </div>
      {items.length > 12 && (
        <button className="profile-text-action" type="button" onClick={() => setIsExpanded((expanded) => !expanded)}>
          {isExpanded ? 'Show fewer skills' : `Show all ${items.length} skills${hiddenCount ? ` (${hiddenCount} more)` : ''}`}
        </button>
      )}
    </>
  )
}

function ExperienceItem({ item, children }) {
  return (
    <div className="profile-enrichment-item">
      <div>
        <strong>{item.title}</strong>
        <span>{experienceMeta(item)}</span>
        {item.description && <p>{item.description}</p>}
        <InlineTags values={item.skills} />
      </div>
      {children}
    </div>
  )
}

function ProjectItem({ item, children }) {
  return (
    <div className="profile-enrichment-item">
      <div>
        <strong>{item.name}</strong>
        <span>{[item.role, item.url].filter(Boolean).join(' · ')}</span>
        {item.description && <p>{item.description}</p>}
        <InlineTags values={item.skills} />
      </div>
      {children}
    </div>
  )
}

function SkillItem({ item, children }) {
  return (
    <div className="profile-enrichment-item">
      <div>
        <strong>{item.name}</strong>
        <span>{[item.category, item.proficiency].filter(Boolean).join(' · ')}</span>
      </div>
      {children}
    </div>
  )
}

function experienceMeta(item) {
  const dates = item.start_date && `${item.start_date}${item.end_date ? ` to ${item.end_date}` : item.is_current ? ' to present' : ''}`
  return [item.company, item.location, dates].filter(Boolean).join(' · ')
}

function InlineActions({ isSaving, onEdit, onDelete }) {
  return (
    <div className="profile-enrichment-actions">
      <button type="button" disabled={isSaving} onClick={onEdit}>Edit</button>
      <button type="button" disabled={isSaving} onClick={onDelete}>Delete</button>
    </div>
  )
}

function InlineTags({ values = [] }) {
  if (!values.length) return null
  return <small>{values.join(', ')}</small>
}

function ExperienceForm({ initialValue, isSaving, submitLabel = 'Add experience', onSubmit, onCancel }) {
  const [form, setForm] = useState(() => ({
    title: initialValue?.title || '',
    company: initialValue?.company || '',
    location: initialValue?.location || '',
    start_date: initialValue?.start_date || '',
    end_date: initialValue?.end_date || '',
    is_current: initialValue?.is_current || false,
    description: initialValue?.description || '',
    skills: initialValue?.skills?.join(', ') || '',
  }))

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    await onSubmit({
      title: form.title.trim(),
      company: blankToNull(form.company),
      location: blankToNull(form.location),
      start_date: blankToNull(form.start_date),
      end_date: form.is_current ? null : blankToNull(form.end_date),
      is_current: form.is_current,
      description: blankToNull(form.description),
      skills: csvValues(form.skills),
    })
    if (!initialValue) {
      setForm({ title: '', company: '', location: '', start_date: '', end_date: '', is_current: false, description: '', skills: '' })
    }
  }

  return (
    <form className="profile-enrichment-form" onSubmit={submit}>
      <div className="profile-form-grid">
        <label>Title<input value={form.title} onChange={(event) => updateField('title', event.target.value)} placeholder="Senior backend engineer" required /></label>
        <label>Company<input value={form.company} onChange={(event) => updateField('company', event.target.value)} placeholder="Acme" /></label>
        <label>Location<input value={form.location} onChange={(event) => updateField('location', event.target.value)} placeholder="Remote, London" /></label>
        <label>Dates<input value={form.start_date} onChange={(event) => updateField('start_date', event.target.value)} placeholder="2022" /></label>
        <label>End<input value={form.end_date} onChange={(event) => updateField('end_date', event.target.value)} placeholder="2024" disabled={form.is_current} /></label>
        <label>Skills<input value={form.skills} onChange={(event) => updateField('skills', event.target.value)} placeholder="Python, Postgres" /></label>
      </div>
      <label className="profile-checkbox-row"><input type="checkbox" checked={form.is_current} onChange={(event) => updateField('is_current', event.target.checked)} />Current role</label>
      <label>Description<textarea value={form.description} onChange={(event) => updateField('description', event.target.value)} rows="3" placeholder="Responsibilities, scope, achievements." /></label>
      <FormActions isSaving={isSaving} submitLabel={submitLabel} disabled={!form.title.trim()} onCancel={onCancel} />
    </form>
  )
}

function ProjectForm({ initialValue, isSaving, submitLabel = 'Add project', onSubmit, onCancel }) {
  const [form, setForm] = useState(() => ({
    name: initialValue?.name || '',
    role: initialValue?.role || '',
    url: initialValue?.url || '',
    description: initialValue?.description || '',
    skills: initialValue?.skills?.join(', ') || '',
  }))

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    await onSubmit({
      name: form.name.trim(),
      role: blankToNull(form.role),
      url: blankToNull(form.url),
      description: blankToNull(form.description),
      skills: csvValues(form.skills),
    })
    if (!initialValue) {
      setForm({ name: '', role: '', url: '', description: '', skills: '' })
    }
  }

  return (
    <form className="profile-enrichment-form" onSubmit={submit}>
      <div className="profile-form-grid">
        <label>Name<input value={form.name} onChange={(event) => updateField('name', event.target.value)} placeholder="Portfolio search" required /></label>
        <label>Role<input value={form.role} onChange={(event) => updateField('role', event.target.value)} placeholder="Creator, lead engineer" /></label>
        <label>Link<input value={form.url} onChange={(event) => updateField('url', event.target.value)} placeholder="https://..." /></label>
        <label>Skills<input value={form.skills} onChange={(event) => updateField('skills', event.target.value)} placeholder="React, FastAPI" /></label>
      </div>
      <label>Description<textarea value={form.description} onChange={(event) => updateField('description', event.target.value)} rows="3" placeholder="What it does and why it matters." /></label>
      <FormActions isSaving={isSaving} submitLabel={submitLabel} disabled={!form.name.trim()} onCancel={onCancel} />
    </form>
  )
}

function SkillForm({ initialValue, isSaving, submitLabel = 'Add skill', onSubmit, onCancel }) {
  const [form, setForm] = useState(() => ({
    name: initialValue?.name || '',
    category: initialValue?.category || '',
    proficiency: initialValue?.proficiency || '',
  }))

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    await onSubmit({
      name: form.name.trim(),
      category: blankToNull(form.category),
      proficiency: blankToNull(form.proficiency),
    })
    if (!initialValue) {
      setForm({ name: '', category: '', proficiency: '' })
    }
  }

  return (
    <form className="profile-enrichment-form" onSubmit={submit}>
      <div className="profile-form-grid">
        <label>Skill<input value={form.name} onChange={(event) => updateField('name', event.target.value)} placeholder="FastAPI" required /></label>
        <label>Category<input value={form.category} onChange={(event) => updateField('category', event.target.value)} placeholder="Backend" /></label>
        <label>Proficiency<input value={form.proficiency} onChange={(event) => updateField('proficiency', event.target.value)} placeholder="Advanced" /></label>
      </div>
      <FormActions isSaving={isSaving} submitLabel={submitLabel} disabled={!form.name.trim()} onCancel={onCancel} />
    </form>
  )
}

function FormActions({ isSaving, submitLabel, disabled, onCancel }) {
  return (
    <div className="profile-enrichment-form-actions">
      <button type="submit" disabled={isSaving || disabled}>{isSaving ? 'Saving...' : submitLabel}</button>
      {onCancel && <button type="button" disabled={isSaving} onClick={onCancel}>Cancel</button>}
    </div>
  )
}

function ProfileForm({ isCreating, onCreateProfile }) {
  const [form, setForm] = useState({
    name: '',
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
    const profileText = manualProfileText(form)
    onCreateProfile({
      name: blankToNull(form.name),
      cv_text: profileText,
      target_roles: csvValues(form.target_roles),
      target_locations: csvValues(form.target_locations),
      skills: csvValues(form.skills),
      seniority: blankToNull(form.seniority),
      preferred_contract_types: csvValues(form.preferred_contract_types),
      remote_preference: blankToNull(form.remote_preference),
    })
    setForm({ name: '', target_roles: '', target_locations: '', skills: '', seniority: '', preferred_contract_types: '', remote_preference: '' })
  }

  const canCreate = Boolean(manualProfileText(form))

  return (
    <form className="profile-form" onSubmit={submit}>
      <div><p>Create profile</p><h2>Manual candidate brief</h2></div>
      <label>Name<input value={form.name} onChange={(event) => updateField('name', event.target.value)} placeholder="Candidate name" /></label>
      <div className="profile-form-grid">
        <label>Target roles<input value={form.target_roles} onChange={(event) => updateField('target_roles', event.target.value)} placeholder="Backend, ML engineer" /></label>
        <label>Locations<input value={form.target_locations} onChange={(event) => updateField('target_locations', event.target.value)} placeholder="Paris, Berlin" /></label>
        <label>Skills<input value={form.skills} onChange={(event) => updateField('skills', event.target.value)} placeholder="Python, FastAPI, SQL" /></label>
        <label>Seniority<input value={form.seniority} onChange={(event) => updateField('seniority', event.target.value)} placeholder="senior" /></label>
        <label>Contracts<input value={form.preferred_contract_types} onChange={(event) => updateField('preferred_contract_types', event.target.value)} placeholder="full-time, contract" /></label>
        <label>Remote preference<input value={form.remote_preference} onChange={(event) => updateField('remote_preference', event.target.value)} placeholder="hybrid" /></label>
      </div>
      <button type="submit" disabled={isCreating || !canCreate}>
        {isCreating ? 'Creating...' : 'Create and select'}
      </button>
    </form>
  )
}

function manualProfileText(form) {
  return [
    form.name && `Name: ${form.name.trim()}`,
    form.target_roles && `Target roles: ${form.target_roles.trim()}`,
    form.target_locations && `Target locations: ${form.target_locations.trim()}`,
    form.skills && `Skills: ${form.skills.trim()}`,
    form.seniority && `Seniority: ${form.seniority.trim()}`,
    form.preferred_contract_types && `Preferred contracts: ${form.preferred_contract_types.trim()}`,
    form.remote_preference && `Remote preference: ${form.remote_preference.trim()}`,
  ].filter(Boolean).join('\n')
}

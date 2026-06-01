import { useEffect, useRef, useState } from 'react'
import { AppSidebar } from '@/components/app-sidebar'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { PanelLeftCloseIcon, PanelLeftOpenIcon } from 'lucide-react'
import { createProfile, listJobs, listProfiles, rankJobsForProfile, sendChatMessage, uploadProfile } from './api.js'

const initialMessages = [
  {
    id: 'intro',
    role: 'assistant',
    content: 'Ask Scout to search indexed jobs or compare opportunities.',
    tool: 'none',
    jobs: [],
    rankedJobs: [],
    warnings: [],
  },
]

const initialThreadId = 'thread-intro'

const initialThreads = [
  {
    id: initialThreadId,
    title: 'Scout advisor',
    detail: 'Ask Scout to search indexed jobs or compare opportunities.',
    time: 'now',
    messages: initialMessages,
  },
]

const STORAGE_KEYS = {
  threads: 'scout.threads',
  activeThreadId: 'scout.activeThreadId',
  selectedProfileId: 'scout.selectedProfileId',
  contextPanelOpen: 'scout.contextPanelOpen',
}

const placeholderViews = {
  jobs: {
    eyebrow: 'Jobs',
    title: 'Imported jobs will live here.',
    body: 'Use the mock provider import command to seed local postings, then ask Scout to search or rank them from the chat.',
    actions: ['uv run python main.py jobs import-mock --fixture packages/services/fixtures/mock_jobs.json', 'uv run python main.py jobs import-mock --count 5 --index'],
  },
  matches: {
    eyebrow: 'Matches',
    title: 'Ranked opportunities are next.',
    body: 'This view will collect profile-aware job matches, evidence, missing skills, and follow-up questions from Scout.',
    actions: ['Select a profile', 'Ask Scout to compare jobs'],
  },
  settings: {
    eyebrow: 'Settings',
    title: 'Configure Scout for local work.',
    body: 'Keep hash embeddings for offline development, or point the API at Gemini/OpenAI once credentials and indexes are ready.',
    actions: ['SCOUT_EMBEDDINGS=hash', 'VITE_API_BASE_URL=http://127.0.0.1:8000'],
  },
  profiles: {
    eyebrow: 'Profiles',
    title: 'Candidate profiles will anchor matching.',
    body: 'The profile area will manage candidate context and CV evidence before Scout uses it to explain job fit.',
    actions: ['Candidate profile', 'CV context'],
  },
}

function App() {
  const [activeView, setActiveView] = useState('chat')
  const [threads, setThreads] = useState(() => {
    const stored = readStoredJson(STORAGE_KEYS.threads, initialThreads)
    return validStoredThreads(stored) ? stored : initialThreads
  })
  const [activeThreadId, setActiveThreadId] = useState(() => readStoredString(STORAGE_KEYS.activeThreadId, initialThreadId))
  const [isContextPanelOpen, setIsContextPanelOpen] = useState(() => readStoredBoolean(STORAGE_KEYS.contextPanelOpen, true))
  const [draft, setDraft] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [jobs, setJobs] = useState([])
  const [isLoadingJobs, setIsLoadingJobs] = useState(false)
  const [jobsError, setJobsError] = useState('')
  const [hasLoadedJobs, setHasLoadedJobs] = useState(false)
  const [profiles, setProfiles] = useState([])
  const [selectedProfileId, setSelectedProfileId] = useState(() => readStoredString(STORAGE_KEYS.selectedProfileId, null))
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(false)
  const [profilesError, setProfilesError] = useState('')
  const [hasLoadedProfiles, setHasLoadedProfiles] = useState(false)
  const [isCreatingProfile, setIsCreatingProfile] = useState(false)
  const [isUploadingProfile, setIsUploadingProfile] = useState(false)
  const [rankedMatches, setRankedMatches] = useState([])
  const [isLoadingMatches, setIsLoadingMatches] = useState(false)
  const [matchesError, setMatchesError] = useState('')
  const [matchesProfileId, setMatchesProfileId] = useState(null)

  const activeThread = threads.find((thread) => thread.id === activeThreadId) || threads[0]
  const messages = activeThread?.messages || []
  const selectedProfile = profiles.find((profile) => profile.id === selectedProfileId) || null

  useEffect(() => {
    writeStoredJson(STORAGE_KEYS.threads, threads)
  }, [threads])

  useEffect(() => {
    writeStoredString(STORAGE_KEYS.activeThreadId, activeThreadId)
  }, [activeThreadId])

  useEffect(() => {
    writeStoredString(STORAGE_KEYS.selectedProfileId, selectedProfileId)
  }, [selectedProfileId])

  useEffect(() => {
    writeStoredJson(STORAGE_KEYS.contextPanelOpen, isContextPanelOpen)
  }, [isContextPanelOpen])

  useEffect(() => {
    if (!threads.some((thread) => thread.id === activeThreadId)) {
      setActiveThreadId(threads[0]?.id || initialThreadId)
    }
  }, [threads, activeThreadId])

  useEffect(() => {
    if (activeView === 'jobs' && !hasLoadedJobs && !isLoadingJobs) {
      loadJobs()
    }
  }, [activeView, hasLoadedJobs, isLoadingJobs])

  useEffect(() => {
    if (activeView === 'profiles' && !hasLoadedProfiles && !isLoadingProfiles) {
      loadProfiles()
    }
  }, [activeView, hasLoadedProfiles, isLoadingProfiles])

  useEffect(() => {
    if (activeView === 'matches' && selectedProfileId && matchesProfileId !== selectedProfileId && !isLoadingMatches) {
      loadMatches(selectedProfileId)
    }
  }, [activeView, selectedProfileId, matchesProfileId, isLoadingMatches])

  async function submitMessage(messageText = draft) {
    const content = messageText.trim()
    if (!content || isSending || !activeThread) return

    const userMessage = { id: crypto.randomUUID(), role: 'user', content }
    updateThread(activeThread.id, (thread) => ({
      ...thread,
      title: thread.title === 'New conversation' ? threadTitle(content) : thread.title,
      detail: content,
      time: 'now',
      messages: [...thread.messages, userMessage],
    }))
    setDraft('')
    setIsSending(true)

    try {
      const history = [...messages, userMessage]
      const response = await sendChatMessage({
        message: content,
        history: history
          .filter((message) => message.role === 'user' || message.role === 'assistant')
          .map((message) => ({ role: message.role, content: message.content })),
        profile_id: selectedProfileId,
        filters: {
          location: null,
          contract_type: null,
          company: null,
          seniority: null,
          remote_policy: null,
        },
        limit: 5,
      })
      updateThread(activeThread.id, (thread) => ({
        ...thread,
        detail: response.message,
        messages: [...thread.messages, assistantMessage(response)],
      }))
    } catch (error) {
      updateThread(activeThread.id, (thread) => ({
        ...thread,
        detail: 'The chat endpoint did not respond.',
        messages: [
          ...thread.messages,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `The chat endpoint did not respond: ${error.message}`,
            tool: 'none',
            jobs: [],
            rankedJobs: [],
            warnings: ['Check that the FastAPI server is running and CORS is configured.'],
          },
        ],
      }))
    } finally {
      setIsSending(false)
    }
  }

  function updateThread(threadId, updater) {
    setThreads((current) => current.map((thread) => (thread.id === threadId ? updater(thread) : thread)))
  }

  function createThread() {
    const id = crypto.randomUUID()
    setThreads((current) => [
      {
        id,
        title: 'New conversation',
        detail: 'Start a focused Scout thread.',
        time: 'new',
        messages: initialMessages,
      },
      ...current,
    ])
    setActiveThreadId(id)
    setActiveView('chat')
    setIsContextPanelOpen(true)
    setDraft('')
  }

  function selectThread(threadId) {
    setActiveThreadId(threadId)
    setActiveView('chat')
    setIsContextPanelOpen(true)
    setDraft('')
  }

  function changeView(view) {
    setActiveView(view)
    setIsContextPanelOpen(view === 'chat')
  }

  async function loadJobs() {
    setIsLoadingJobs(true)
    setJobsError('')
    try {
      const loadedJobs = await listJobs({ limit: 50 })
      setJobs(loadedJobs)
      setHasLoadedJobs(true)
    } catch (error) {
      setJobsError(error.message)
      setHasLoadedJobs(true)
    } finally {
      setIsLoadingJobs(false)
    }
  }

  async function loadProfiles() {
    setIsLoadingProfiles(true)
    setProfilesError('')
    try {
      const loadedProfiles = await listProfiles({ limit: 50 })
      setProfiles(loadedProfiles)
      setSelectedProfileId((current) => {
        if (current && loadedProfiles.some((profile) => profile.id === current)) {
          return current
        }
        return loadedProfiles[0]?.id || null
      })
      setHasLoadedProfiles(true)
    } catch (error) {
      setProfilesError(error.message)
      setHasLoadedProfiles(true)
    } finally {
      setIsLoadingProfiles(false)
    }
  }

  async function submitProfile(profile) {
    setIsCreatingProfile(true)
    setProfilesError('')
    try {
      const created = await createProfile(profile)
      setProfiles((current) => [created, ...current])
      setSelectedProfileId(created.id)
      setHasLoadedProfiles(true)
    } catch (error) {
      setProfilesError(error.message)
    } finally {
      setIsCreatingProfile(false)
    }
  }

  async function submitProfileUpload(formData) {
    setIsUploadingProfile(true)
    setProfilesError('')
    try {
      const created = await uploadProfile(formData)
      setProfiles((current) => [created, ...current])
      setSelectedProfileId(created.id)
      setHasLoadedProfiles(true)
    } catch (error) {
      setProfilesError(error.message)
    } finally {
      setIsUploadingProfile(false)
    }
  }

  async function loadMatches(profileId = selectedProfileId) {
    if (!profileId) return
    setIsLoadingMatches(true)
    setMatchesError('')
    try {
      const ranked = await rankJobsForProfile({ profileId, limit: 10 })
      setRankedMatches(ranked)
      setMatchesProfileId(profileId)
    } catch (error) {
      setMatchesError(error.message)
      setRankedMatches([])
      setMatchesProfileId(profileId)
    } finally {
      setIsLoadingMatches(false)
    }
  }

  return (
    <TooltipProvider>
      <SidebarProvider
        open={activeView === 'chat' && isContextPanelOpen}
        onOpenChange={setIsContextPanelOpen}
        style={{
          '--sidebar-width': '22rem',
          '--sidebar-width-icon': '3.25rem',
        }}
      >
        <AppSidebar
          activeView={activeView}
          threads={threads}
          activeThreadId={activeThreadId}
          onViewChange={changeView}
          onThreadSelect={selectThread}
          onNewThread={createThread}
        />
        <SidebarInset className="chat-root">
          <main className={activeView === 'chat' ? 'chat-page' : 'workspace-page'}>
            {activeView === 'chat' && (
              <ChatView messages={messages} draft={draft} isSending={isSending} selectedProfile={selectedProfile} onDraftChange={setDraft} onSubmit={submitMessage} />
            )}
            {activeView === 'chat' && (
              <button
                className="chat-context-toggle"
                type="button"
                onClick={() => setIsContextPanelOpen((open) => !open)}
                aria-label={isContextPanelOpen ? 'Hide conversation list' : 'Show conversation list'}
                title={isContextPanelOpen ? 'Hide conversation list' : 'Show conversation list'}
              >
                {isContextPanelOpen ? <PanelLeftCloseIcon className="size-4" /> : <PanelLeftOpenIcon className="size-4" />}
              </button>
            )}
            {activeView === 'jobs' && <JobsView jobs={jobs} isLoading={isLoadingJobs} error={jobsError} onRefresh={loadJobs} />}
            {activeView === 'profiles' && (
              <ProfilesView
                profiles={profiles}
                selectedProfileId={selectedProfileId}
                isLoading={isLoadingProfiles}
                isCreating={isCreatingProfile}
                isUploading={isUploadingProfile}
                error={profilesError}
                onRefresh={loadProfiles}
                onSelectProfile={setSelectedProfileId}
                onCreateProfile={submitProfile}
                onUploadProfile={submitProfileUpload}
              />
            )}
            {activeView === 'matches' && (
              <MatchesView
                selectedProfile={selectedProfile}
                matches={rankedMatches}
                isLoading={isLoadingMatches}
                error={matchesError}
                onRefresh={() => loadMatches()}
                onOpenProfiles={() => changeView('profiles')}
              />
            )}
            {activeView !== 'chat' && activeView !== 'jobs' && activeView !== 'profiles' && activeView !== 'matches' && <PlaceholderView view={placeholderViews[activeView]} />}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}

function JobsView({ jobs, isLoading, error, onRefresh }) {
  return (
    <section className="jobs-view" aria-label="Imported jobs">
      <header className="jobs-header">
        <div>
          <p>Jobs</p>
          <h1>Imported opportunities</h1>
          <span>{jobs.length ? `${jobs.length} postings ready for Scout search and matching.` : 'Seed jobs from the CLI, then refresh this page.'}</span>
        </div>
        <button type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </header>

      {error && (
        <div className="jobs-state warning-state" role="alert">
          <strong>Could not load jobs.</strong>
          <span>{error}</span>
          <code>uv run uvicorn apps.api.main:app --reload</code>
        </div>
      )}

      {isLoading && !jobs.length && (
        <div className="jobs-state">
          <strong>Loading jobs...</strong>
          <span>Scout is asking the API for the latest imported postings.</span>
        </div>
      )}

      {!isLoading && !error && jobs.length === 0 && (
        <div className="jobs-state">
          <strong>No jobs imported yet.</strong>
          <span>Run a mock import, then press Refresh.</span>
          <code>uv run python main.py jobs import-mock --fixture packages/services/fixtures/mock_jobs.json</code>
        </div>
      )}

      {jobs.length > 0 && (
        <div className="jobs-grid">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} ranked={false} />
          ))}
        </div>
      )}
    </section>
  )
}

function MatchesView({ selectedProfile, matches, isLoading, error, onRefresh, onOpenProfiles }) {
  return (
    <section className="matches-view" aria-label="Ranked matches">
      <header className="matches-header">
        <div>
          <p>Matches</p>
          <h1>Ranked fit</h1>
          <span>
            {selectedProfile
              ? `Ranking imported jobs against ${profileName(selectedProfile)}.`
              : 'Select a candidate profile to rank imported jobs.'}
          </span>
        </div>
        {selectedProfile ? (
          <button type="button" onClick={onRefresh} disabled={isLoading}>
            {isLoading ? 'Ranking...' : 'Rerank jobs'}
          </button>
        ) : (
          <button type="button" onClick={onOpenProfiles}>Select profile</button>
        )}
      </header>

      {!selectedProfile && (
        <div className="matches-state">
          <strong>No profile selected.</strong>
          <span>Create or select a profile before viewing ranked matches.</span>
        </div>
      )}

      {error && (
        <div className="matches-state warning-state" role="alert">
          <strong>Could not rank jobs.</strong>
          <span>{error}</span>
        </div>
      )}

      {selectedProfile && isLoading && !matches.length && (
        <div className="matches-state">
          <strong>Ranking jobs...</strong>
          <span>Scout is comparing job evidence against the selected profile.</span>
        </div>
      )}

      {selectedProfile && !isLoading && !error && matches.length === 0 && (
        <div className="matches-state">
          <strong>No ranked matches yet.</strong>
          <span>Import and index jobs, then run the ranking again.</span>
        </div>
      )}

      {matches.length > 0 && (
        <div className="matches-grid">
          {matches.map((match, index) => (
            <MatchCard key={match.job_id} match={match} rank={index + 1} />
          ))}
        </div>
      )}
    </section>
  )
}

function MatchCard({ match, rank }) {
  return (
    <article className="match-card">
      <div className="match-rank">#{rank}</div>
      <div className="match-card-main">
        <div className="match-card-header">
          <div>
            <h2>{match.title}</h2>
            <p>{[match.company, match.location, match.contract_type].filter(Boolean).join(' / ') || 'Unspecified'}</p>
          </div>
          <span>{match.final_score.toFixed(2)}</span>
        </div>

        <div className="match-score-grid">
          <ScorePill label="Vector" value={match.vector_score} />
          <ScorePill label="Skills" value={match.skill_overlap_score} />
          <ScorePill label="Location" value={match.location_score} />
          <ScorePill label="Contract" value={match.contract_type_score} />
        </div>

        <MatchChipGroup label="Matched skills" values={match.matched_skills} />
        <MatchChipGroup label="Missing skills" values={match.missing_skills} muted />

        {match.evidence?.length > 0 && (
          <div className="match-evidence">
            <small>Evidence</small>
            {match.evidence.slice(0, 2).map((item) => (
              <blockquote key={item.chunk_id}>{item.content}</blockquote>
            ))}
          </div>
        )}

        {match.url && (
          <a href={match.url} target="_blank" rel="noreferrer">
            Open posting
          </a>
        )}
      </div>
    </article>
  )
}

function ScorePill({ label, value }) {
  return (
    <div className="score-pill">
      <small>{label}</small>
      <strong>{typeof value === 'number' ? value.toFixed(2) : '0.00'}</strong>
    </div>
  )
}

function MatchChipGroup({ label, values = [], muted = false }) {
  if (!values.length) return null
  return (
    <div className="match-chip-group" data-muted={muted}>
      <small>{label}</small>
      <div className="tag-row">
        {values.map((value) => (
          <span key={value}>{value}</span>
        ))}
      </div>
    </div>
  )
}

function ProfilesView({ profiles, selectedProfileId, isLoading, isCreating, isUploading, error, onRefresh, onSelectProfile, onCreateProfile, onUploadProfile }) {
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
        <input
          type="file"
          accept=".pdf,application/pdf"
          required
          onChange={(event) => updateField('file', event.target.files?.[0] || null)}
        />
        <small>{form.file ? `${form.file.name} (${Math.ceil(form.file.size / 1024)} KB)` : 'PDF only, up to 5 MB.'}</small>
      </label>

      <label className="profile-checkbox-row">
        <input type="checkbox" checked={form.extract_profile} onChange={(event) => updateField('extract_profile', event.target.checked)} />
        Extract profile fields with the configured model
      </label>

      <div className="profile-form-grid">
        <label>
          Name
          <input value={form.name} onChange={(event) => updateField('name', event.target.value)} placeholder="Optional display name" />
        </label>
        <label>
          Target roles
          <input value={form.target_roles} onChange={(event) => updateField('target_roles', event.target.value)} placeholder="Backend, ML engineer" />
        </label>
        <label>
          Locations
          <input value={form.target_locations} onChange={(event) => updateField('target_locations', event.target.value)} placeholder="Paris, Berlin" />
        </label>
        <label>
          Skills
          <input value={form.skills} onChange={(event) => updateField('skills', event.target.value)} placeholder="Python, FastAPI, SQL" />
        </label>
        <label>
          Seniority
          <input value={form.seniority} onChange={(event) => updateField('seniority', event.target.value)} placeholder="senior" />
        </label>
        <label>
          Remote preference
          <input value={form.remote_preference} onChange={(event) => updateField('remote_preference', event.target.value)} placeholder="hybrid" />
        </label>
      </div>

      <label>
        Contracts
        <input value={form.preferred_contract_types} onChange={(event) => updateField('preferred_contract_types', event.target.value)} placeholder="full-time, contract" />
      </label>

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
        <div>
          <small>Seniority</small>
          <strong>{profile.seniority || 'Any'}</strong>
        </div>
        <div>
          <small>Contracts</small>
          <strong>{profile.preferred_contract_types?.join(', ') || 'Any'}</strong>
        </div>
        <div>
          <small>Remote</small>
          <strong>{profile.remote_preference || 'Any'}</strong>
        </div>
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
    setForm({
      name: '',
      cv_text: '',
      target_roles: '',
      target_locations: '',
      skills: '',
      seniority: '',
      preferred_contract_types: '',
      remote_preference: '',
    })
  }

  return (
    <form className="profile-form" onSubmit={submit}>
      <div>
        <p>Create profile</p>
        <h2>Manual candidate brief</h2>
      </div>
      <label>
        Name
        <input value={form.name} onChange={(event) => updateField('name', event.target.value)} placeholder="Candidate name" />
      </label>
      <label>
        CV text
        <textarea value={form.cv_text} onChange={(event) => updateField('cv_text', event.target.value)} placeholder="Paste a concise CV summary, experience, or goals." rows="5" required />
      </label>
      <div className="profile-form-grid">
        <label>
          Target roles
          <input value={form.target_roles} onChange={(event) => updateField('target_roles', event.target.value)} placeholder="Backend, ML engineer" />
        </label>
        <label>
          Locations
          <input value={form.target_locations} onChange={(event) => updateField('target_locations', event.target.value)} placeholder="Paris, Berlin" />
        </label>
        <label>
          Skills
          <input value={form.skills} onChange={(event) => updateField('skills', event.target.value)} placeholder="Python, FastAPI, SQL" />
        </label>
        <label>
          Seniority
          <input value={form.seniority} onChange={(event) => updateField('seniority', event.target.value)} placeholder="senior" />
        </label>
        <label>
          Contracts
          <input value={form.preferred_contract_types} onChange={(event) => updateField('preferred_contract_types', event.target.value)} placeholder="full-time, contract" />
        </label>
        <label>
          Remote preference
          <input value={form.remote_preference} onChange={(event) => updateField('remote_preference', event.target.value)} placeholder="hybrid" />
        </label>
      </div>
      <button type="submit" disabled={isCreating || !form.cv_text.trim()}>
        {isCreating ? 'Creating...' : 'Create and select'}
      </button>
    </form>
  )
}

function ChatView({ messages, draft, isSending, selectedProfile, onDraftChange, onSubmit }) {
  const hasMountedRef = useRef(false)

  useEffect(() => {
    if (!hasMountedRef.current) {
      hasMountedRef.current = true
      return
    }

    const chatPage = document.querySelector('.chat-page')
    chatPage?.scrollTo({
      top: chatPage.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages.length, isSending])

  return (
    <section className="chat-panel" aria-label="Scout conversation">
      <div className="transcript">
        {selectedProfile && <div className="profile-chat-chip">Matching as {profileName(selectedProfile)}</div>}
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {isSending && <p className="thinking">Scout is thinking...</p>}
      </div>

      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit()
        }}
      >
        <textarea value={draft} onChange={(event) => onDraftChange(event.target.value)} placeholder="Ask Scout..." rows="2" />
        <button type="submit" disabled={isSending || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  )
}

function PlaceholderView({ view }) {
  return (
    <section className="workspace-card" aria-label={view.eyebrow}>
      <p>{view.eyebrow}</p>
      <h1>{view.title}</h1>
      <span>{view.body}</span>
      <div className="workspace-actions">
        {view.actions.map((action) => (
          <code key={action}>{action}</code>
        ))}
      </div>
    </section>
  )
}

function ChatMessage({ message }) {
  const results = message.rankedJobs?.length ? message.rankedJobs : message.jobs || []
  return (
    <article className={`message ${message.role}`}>
      <div className="message-meta">
        <span>{message.role === 'user' ? 'You' : 'Scout'}</span>
        {message.tool && <code>{message.tool}</code>}
      </div>
      <p>{message.content}</p>
      {message.warnings?.map((warning) => (
        <div className="warning" key={warning}>
          {warning}
        </div>
      ))}
      {results.length > 0 && (
        <div className="result-grid">
          {results.map((job) => (
            <JobCard key={`${job.job_id}-${job.chunk_id || 'ranked'}`} job={job} ranked={Boolean(message.rankedJobs?.length)} />
          ))}
        </div>
      )}
    </article>
  )
}

function JobCard({ job, ranked }) {
  const score = ranked ? job.final_score : job.score
  const content = job.content || job.description
  return (
    <section className="job-card">
      <div className="job-card-header">
        <div>
          <h3>{job.title}</h3>
          <p>{[job.company, job.location, job.contract_type].filter(Boolean).join(' / ') || 'Unspecified'}</p>
        </div>
        {typeof score === 'number' && <span className="score">{score.toFixed(2)}</span>}
      </div>
      {ranked ? (
        <p className="evidence">Matched skills: {job.matched_skills?.join(', ') || 'None listed'}</p>
      ) : (
        <p className="evidence">{content}</p>
      )}
      <div className="tag-row">
        {(job.skills || []).slice(0, 5).map((skill) => (
          <span key={skill}>{skill}</span>
        ))}
      </div>
      {job.url && (
        <a href={job.url} target="_blank" rel="noreferrer">
          Open posting
        </a>
      )}
    </section>
  )
}

function assistantMessage(response) {
  return {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: response.message,
    tool: response.tool,
    jobs: response.jobs || [],
    rankedJobs: response.ranked_jobs || [],
    warnings: response.warnings || [],
  }
}

function threadTitle(content) {
  return content.length > 38 ? `${content.slice(0, 35)}...` : content
}

function profileName(profile) {
  return profile.name || profile.target_roles?.[0] || 'Candidate profile'
}

function csvValues(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function blankToNull(value) {
  const trimmed = value.trim()
  return trimmed || null
}

function readStoredJson(key, fallback) {
  try {
    const value = window.localStorage.getItem(key)
    return value ? JSON.parse(value) : fallback
  } catch {
    return fallback
  }
}

function writeStoredJson(key, value) {
  window.localStorage.setItem(key, JSON.stringify(value))
}

function readStoredString(key, fallback = null) {
  return window.localStorage.getItem(key) || fallback
}

function writeStoredString(key, value) {
  if (value) {
    window.localStorage.setItem(key, value)
  } else {
    window.localStorage.removeItem(key)
  }
}

function readStoredBoolean(key, fallback) {
  const value = window.localStorage.getItem(key)
  if (value === 'true') return true
  if (value === 'false') return false
  return fallback
}

function validStoredThreads(value) {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((thread) => {
      return typeof thread.id === 'string' && typeof thread.title === 'string' && Array.isArray(thread.messages)
    })
  )
}

export default App

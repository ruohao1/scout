import { useEffect, useState } from 'react'
import { AppSidebar } from '@/components/app-sidebar'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { PanelLeftCloseIcon, PanelLeftOpenIcon } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  attachProfileCv,
  createProfile,
  createProfileExperience,
  createProfileProject,
  createProfileSkill,
  deleteProfileExperience,
  deleteProfileProject,
  deleteProfileSkill,
  getProfileEnrichment,
  listJobs,
  listProfiles,
  rankJobsForProfile,
  sendChatMessageStream,
  uploadProfile,
  updateProfileExperience,
  updateProfileProject,
  updateProfileSkill,
} from './api.js'
import { applyChatStreamEvent, failRunningActivities } from './features/chat/chatStreamReducer.js'
import { ChatView } from './features/chat/ChatView.jsx'
import { JobsView } from './features/jobs/JobsView.jsx'
import { MatchesView } from './features/matches/MatchesView.jsx'
import { ProfilesView } from './features/profiles/ProfilesView.jsx'
import { PlaceholderView } from './features/workspace/PlaceholderView.jsx'
import { readStoredBoolean, readStoredJson, readStoredString, writeStoredJson, writeStoredString } from './lib/storage.js'

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

const routeByView = {
  chat: '/chat',
  jobs: '/jobs',
  matches: '/matches',
  profiles: '/profiles',
  settings: '/settings',
}

const viewByRoute = Object.fromEntries(Object.entries(routeByView).map(([view, route]) => [route, view]))

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
    body: 'The profile area will manage candidate context before Scout uses it to explain job fit.',
    actions: ['Candidate profile', 'Structured context'],
  },
}

function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const activeView = viewByRoute[location.pathname] || 'chat'
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
  const [isAttachingProfileCv, setIsAttachingProfileCv] = useState(false)
  const [profileEnrichment, setProfileEnrichment] = useState({ experiences: [], projects: [], enriched_skills: [] })
  const [enrichmentProfileId, setEnrichmentProfileId] = useState(null)
  const [isLoadingEnrichment, setIsLoadingEnrichment] = useState(false)
  const [isSavingEnrichment, setIsSavingEnrichment] = useState(false)
  const [rankedMatches, setRankedMatches] = useState([])
  const [isLoadingMatches, setIsLoadingMatches] = useState(false)
  const [matchesError, setMatchesError] = useState('')
  const [matchesProfileId, setMatchesProfileId] = useState(null)

  const activeThread = threads.find((thread) => thread.id === activeThreadId) || threads[0]
  const messages = activeThread?.messages || []
  const selectedProfile = profiles.find((profile) => profile.id === selectedProfileId) || null
  const selectedProfileExists = Boolean(selectedProfileId && profiles.some((profile) => profile.id === selectedProfileId))

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
    if (location.pathname === '/') {
      navigate('/chat', { replace: true })
      return
    }
    if (!viewByRoute[location.pathname]) {
      navigate('/chat', { replace: true })
    }
  }, [location.pathname, navigate])

  useEffect(() => {
    if (activeView === 'jobs' && !hasLoadedJobs && !isLoadingJobs) {
      loadJobs()
    }
  }, [activeView, hasLoadedJobs, isLoadingJobs])

  useEffect(() => {
    if ((activeView === 'profiles' || activeView === 'matches') && !hasLoadedProfiles && !isLoadingProfiles) {
      loadProfiles()
    }
  }, [activeView, hasLoadedProfiles, isLoadingProfiles])

  useEffect(() => {
    if (activeView === 'profiles' && hasLoadedProfiles && selectedProfileExists && enrichmentProfileId !== selectedProfileId && !isLoadingEnrichment) {
      loadProfileEnrichment(selectedProfileId)
    }
  }, [activeView, hasLoadedProfiles, selectedProfileExists, selectedProfileId, enrichmentProfileId, isLoadingEnrichment])

  useEffect(() => {
    if (activeView === 'matches' && hasLoadedProfiles && !selectedProfileExists) {
      setRankedMatches([])
      setMatchesProfileId(null)
      return
    }
    if (activeView === 'matches' && hasLoadedProfiles && selectedProfileExists && matchesProfileId !== selectedProfileId && !isLoadingMatches) {
      loadMatches(selectedProfileId)
    }
  }, [activeView, hasLoadedProfiles, selectedProfileExists, selectedProfileId, matchesProfileId, isLoadingMatches])

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

    const assistantId = crypto.randomUUID()
    updateThread(activeThread.id, (thread) => ({
      ...thread,
      detail: 'Scout is working...',
      messages: [
        ...thread.messages,
        {
          id: assistantId,
          role: 'assistant',
          content: '',
          tool: 'none',
          jobs: [],
          rankedJobs: [],
          warnings: [],
          status: 'running',
          activities: [],
          activityCollapsed: false,
        },
      ],
    }))

    try {
      const history = [...messages, userMessage]
      const payload = {
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
      }

      await sendChatMessageStream(payload, (event) => {
        updateThread(activeThread.id, (thread) => applyChatStreamEvent(thread, assistantId, event))
      })
    } catch (error) {
      updateThread(activeThread.id, (thread) => ({
        ...thread,
        detail: 'The chat endpoint did not respond.',
        messages: thread.messages.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content: `The chat stream stopped unexpectedly: ${error.message}`,
                status: 'failed',
                activityCollapsed: false,
                warnings: ['Check that the FastAPI server is running and CORS is configured.'],
                activities: failRunningActivities(message.activities || [], error.message),
              }
            : message,
        ),
      }))
    } finally {
      setIsSending(false)
    }
  }

  function updateThread(threadId, updater) {
    setThreads((current) => current.map((thread) => (thread.id === threadId ? updater(thread) : thread)))
  }

  function freshThread() {
    return {
      id: crypto.randomUUID(),
      title: 'New conversation',
      detail: 'Start a focused Scout thread.',
      time: 'new',
      messages: cloneMessages(initialMessages),
    }
  }

  function createThread() {
    const thread = freshThread()
    setThreads((current) => [
      thread,
      ...current,
    ])
    setActiveThreadId(thread.id)
    navigate('/chat')
    setIsContextPanelOpen(true)
    setDraft('')
  }

  function renameThread(threadId, title) {
    const nextTitle = title.trim()
    if (!nextTitle) return

    updateThread(threadId, (thread) => ({
      ...thread,
      title: nextTitle,
    }))
  }

  function duplicateThread(threadId) {
    const source = threads.find((thread) => thread.id === threadId)
    if (!source) return

    const duplicate = {
      ...source,
      id: crypto.randomUUID(),
      title: `${source.title} copy`,
      time: 'new',
      messages: cloneMessages(source.messages),
    }

    const sourceIndex = threads.findIndex((thread) => thread.id === threadId)
    setThreads([...threads.slice(0, sourceIndex + 1), duplicate, ...threads.slice(sourceIndex + 1)])
    setActiveThreadId(duplicate.id)
    navigate('/chat')
    setIsContextPanelOpen(true)
    setDraft('')
  }

  function deleteThread(threadId) {
    if (!threads.some((thread) => thread.id === threadId)) return

    if (threads.length === 1) {
      const replacement = freshThread()
      setThreads([replacement])
      setActiveThreadId(replacement.id)
      navigate('/chat')
      setIsContextPanelOpen(true)
      setDraft('')
      return
    }

    const nextThreads = threads.filter((thread) => thread.id !== threadId)
    setThreads(nextThreads)
    if (threadId === activeThreadId) {
      setActiveThreadId(nextThreads[0].id)
      setDraft('')
    }
  }

  function selectThread(threadId) {
    setActiveThreadId(threadId)
    navigate('/chat')
    setIsContextPanelOpen(true)
    setDraft('')
  }

  function changeView(view) {
    navigate(routeByView[view] || '/chat')
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

  async function uploadCvProfile(file) {
    if (!file || isCreatingProfile) return
    const formData = new FormData()
    formData.append('file', file)
    formData.append('extract_profile', 'true')

    setIsCreatingProfile(true)
    setProfilesError('')
    try {
      const created = await uploadProfile(formData)
      setProfiles((current) => [created, ...current.filter((profile) => profile.id !== created.id)])
      setSelectedProfileId(created.id)
      setHasLoadedProfiles(true)
      await loadProfileEnrichment(created.id)
      setMatchesProfileId(null)
    } catch (error) {
      setProfilesError(error.message)
    } finally {
      setIsCreatingProfile(false)
    }
  }

  async function attachCvToSelectedProfile(file) {
    if (!selectedProfileId || !file || isAttachingProfileCv) return
    const formData = new FormData()
    formData.append('file', file)
    formData.append('extract_profile', 'true')

    setIsAttachingProfileCv(true)
    setProfilesError('')
    try {
      const updated = await attachProfileCv(selectedProfileId, formData)
      setProfiles((current) => current.map((profile) => (profile.id === updated.id ? updated : profile)))
      setHasLoadedProfiles(true)
      await loadProfileEnrichment(selectedProfileId)
      setMatchesProfileId(null)
    } catch (error) {
      setProfilesError(error.message)
    } finally {
      setIsAttachingProfileCv(false)
    }
  }

  async function loadProfileEnrichment(profileId = selectedProfileId) {
    if (!profileId) {
      setProfileEnrichment({ experiences: [], projects: [], enriched_skills: [] })
      setEnrichmentProfileId(null)
      return
    }
    setIsLoadingEnrichment(true)
    setProfilesError('')
    try {
      const enrichment = await getProfileEnrichment(profileId)
      setProfileEnrichment(enrichment)
      setEnrichmentProfileId(profileId)
    } catch (error) {
      setProfilesError(error.message)
      setProfileEnrichment({ experiences: [], projects: [], enriched_skills: [] })
      setEnrichmentProfileId(profileId)
    } finally {
      setIsLoadingEnrichment(false)
    }
  }

  async function mutateProfileEnrichment(action) {
    if (!selectedProfileId || isSavingEnrichment) return
    setIsSavingEnrichment(true)
    setProfilesError('')
    try {
      await action(selectedProfileId)
      await loadProfileEnrichment(selectedProfileId)
      setMatchesProfileId(null)
    } catch (error) {
      setProfilesError(error.message)
    } finally {
      setIsSavingEnrichment(false)
    }
  }

  function submitProfileExperience(experience) {
    return mutateProfileEnrichment((profileId) => createProfileExperience(profileId, experience))
  }

  function saveProfileExperience(experienceId, experience) {
    return mutateProfileEnrichment((profileId) => updateProfileExperience(profileId, experienceId, experience))
  }

  function removeProfileExperience(experienceId) {
    return mutateProfileEnrichment((profileId) => deleteProfileExperience(profileId, experienceId))
  }

  function submitProfileProject(project) {
    return mutateProfileEnrichment((profileId) => createProfileProject(profileId, project))
  }

  function saveProfileProject(projectId, project) {
    return mutateProfileEnrichment((profileId) => updateProfileProject(profileId, projectId, project))
  }

  function removeProfileProject(projectId) {
    return mutateProfileEnrichment((profileId) => deleteProfileProject(profileId, projectId))
  }

  function submitProfileSkill(skill) {
    return mutateProfileEnrichment((profileId) => createProfileSkill(profileId, skill))
  }

  function saveProfileSkill(skillId, skill) {
    return mutateProfileEnrichment((profileId) => updateProfileSkill(profileId, skillId, skill))
  }

  function removeProfileSkill(skillId) {
    return mutateProfileEnrichment((profileId) => deleteProfileSkill(profileId, skillId))
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
        open={(activeView === 'chat' || activeView === 'profiles') && isContextPanelOpen}
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
          profiles={profiles}
          selectedProfileId={selectedProfileId}
          isLoadingProfiles={isLoadingProfiles}
          onViewChange={changeView}
          onThreadSelect={selectThread}
          onNewThread={createThread}
          onThreadRename={renameThread}
          onThreadDuplicate={duplicateThread}
          onThreadDelete={deleteThread}
          onProfileSelect={setSelectedProfileId}
          onProfilesRefresh={loadProfiles}
        />
        <SidebarInset className="chat-root">
          <main className={activeView === 'chat' ? 'chat-page' : 'workspace-page'}>
            {activeView === 'chat' && <ChatView messages={messages} draft={draft} isSending={isSending} selectedProfile={selectedProfile} onDraftChange={setDraft} onSubmit={submitMessage} />}
            {(activeView === 'chat' || activeView === 'profiles') && (
              <button
                className="chat-context-toggle"
                type="button"
                onClick={() => setIsContextPanelOpen((open) => !open)}
                aria-label={contextPanelToggleLabel(activeView, isContextPanelOpen)}
                title={contextPanelToggleLabel(activeView, isContextPanelOpen)}
              >
                {isContextPanelOpen ? <PanelLeftCloseIcon className="size-4" /> : <PanelLeftOpenIcon className="size-4" />}
              </button>
            )}
            {activeView === 'jobs' && <JobsView jobs={jobs} isLoading={isLoadingJobs} error={jobsError} onRefresh={loadJobs} />}
            {activeView === 'profiles' && (
              <ProfilesView
                profiles={profiles}
                selectedProfileId={selectedProfileId}
                isCreating={isCreatingProfile}
                isAttachingCv={isAttachingProfileCv}
                enrichment={profileEnrichment}
                isLoadingEnrichment={isLoadingEnrichment}
                isSavingEnrichment={isSavingEnrichment}
                error={profilesError}
                onCreateProfile={submitProfile}
                onUploadCvProfile={uploadCvProfile}
                onAttachCv={attachCvToSelectedProfile}
                onCreateExperience={submitProfileExperience}
                onUpdateExperience={saveProfileExperience}
                onDeleteExperience={removeProfileExperience}
                onCreateProject={submitProfileProject}
                onUpdateProject={saveProfileProject}
                onDeleteProject={removeProfileProject}
                onCreateSkill={submitProfileSkill}
                onUpdateSkill={saveProfileSkill}
                onDeleteSkill={removeProfileSkill}
              />
            )}
            {activeView === 'matches' && (
              <MatchesView selectedProfile={selectedProfile} matches={rankedMatches} isLoading={isLoadingMatches} error={matchesError} onRefresh={() => selectedProfileExists && loadMatches(selectedProfileId)} onOpenProfiles={() => changeView('profiles')} />
            )}
            {activeView !== 'chat' && activeView !== 'jobs' && activeView !== 'profiles' && activeView !== 'matches' && <PlaceholderView view={placeholderViews[activeView]} />}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}

function contextPanelToggleLabel(activeView, isOpen) {
  if (activeView === 'profiles') {
    return isOpen ? 'Hide profile list' : 'Show profile list'
  }
  return isOpen ? 'Hide conversation list' : 'Show conversation list'
}

function threadTitle(content) {
  return content.length > 38 ? `${content.slice(0, 35)}...` : content
}

function cloneMessages(messages) {
  return messages.map((message) => ({
    ...message,
    jobs: message.jobs ? [...message.jobs] : message.jobs,
    rankedJobs: message.rankedJobs ? [...message.rankedJobs] : message.rankedJobs,
    warnings: message.warnings ? [...message.warnings] : message.warnings,
    activities: message.activities ? message.activities.map((activity) => ({ ...activity })) : message.activities,
  }))
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

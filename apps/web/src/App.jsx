import { useEffect, useState } from 'react'
import { AppSidebar } from '@/components/app-sidebar'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { PanelLeftCloseIcon, PanelLeftOpenIcon } from 'lucide-react'
import { createProfile, listJobs, listProfiles, rankJobsForProfile, sendChatMessageStream, uploadProfile } from './api.js'
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
        <AppSidebar activeView={activeView} threads={threads} activeThreadId={activeThreadId} onViewChange={changeView} onThreadSelect={selectThread} onNewThread={createThread} />
        <SidebarInset className="chat-root">
          <main className={activeView === 'chat' ? 'chat-page' : 'workspace-page'}>
            {activeView === 'chat' && <ChatView messages={messages} draft={draft} isSending={isSending} selectedProfile={selectedProfile} onDraftChange={setDraft} onSubmit={submitMessage} />}
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
              <MatchesView selectedProfile={selectedProfile} matches={rankedMatches} isLoading={isLoadingMatches} error={matchesError} onRefresh={() => loadMatches()} onOpenProfiles={() => changeView('profiles')} />
            )}
            {activeView !== 'chat' && activeView !== 'jobs' && activeView !== 'profiles' && activeView !== 'matches' && <PlaceholderView view={placeholderViews[activeView]} />}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}

function threadTitle(content) {
  return content.length > 38 ? `${content.slice(0, 35)}...` : content
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

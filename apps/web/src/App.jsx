import { useEffect, useState } from 'react'
import { AppSidebar } from '@/components/app-sidebar'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { PanelLeftCloseIcon, PanelLeftOpenIcon } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  getJob,
  listTargetProfiles,
  listJobs,
  rankJobsForTargetProfile,
  sendChatMessageStream,
} from './api.js'
import { applyChatStreamEvent, failRunningActivities } from './features/chat/chatStreamReducer.js'
import { CandidateView } from './features/candidate/CandidateView.jsx'
import { ChatView } from './features/chat/ChatView.jsx'
import { JobsView } from './features/jobs/JobsView.jsx'
import { MatchesView } from './features/matches/MatchesView.jsx'
import { SettingsView } from './features/settings/SettingsView.jsx'
import { TargetProfilesView } from './features/target-profiles/TargetProfilesView.jsx'
import { PlaceholderView } from './features/workspace/PlaceholderView.jsx'
import { ACTIVE_TARGET_PROFILE_ID_KEY, readStoredBoolean, readStoredJson, readStoredString, writeStoredJson, writeStoredString } from './lib/storage.js'

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
  selectedProfileId: ACTIVE_TARGET_PROFILE_ID_KEY,
  contextPanelOpen: 'scout.contextPanelOpen',
}

const routeByView = {
  chat: '/chat',
  jobs: '/jobs',
  matches: '/matches',
  candidate: '/candidate',
  targetProfiles: '/target-profiles',
  settings: '/settings',
}

const viewByRoute = {
  ...Object.fromEntries(Object.entries(routeByView).map(([view, route]) => [route, view])),
  '/profiles': 'candidate',
}

const placeholderViews = {
  jobs: {
    eyebrow: 'Jobs',
    title: 'Imported jobs will live here.',
    body: 'Import live jobs through Scout chat, JobSpy, or Adzuna, then ask Scout to search or rank them.',
    actions: ['Ask for latest jobs', 'Import Adzuna jobs'],
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
  candidate: {
    eyebrow: 'Candidate',
    title: 'Candidate knowledge anchors matching.',
    body: 'The candidate workspace manages evidence and target profiles before Scout ranks jobs.',
    actions: ['Candidate evidence', 'Target profiles'],
  },
  targetProfiles: {
    eyebrow: 'Target Profiles',
    title: 'Personas shape matching.',
    body: 'Target profiles select candidate evidence, weights, and keywords for each job-search direction.',
    actions: ['Evidence weights', 'Search personas'],
  },
}

function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const selectedJobId = selectedJobIdFromPath(location.pathname)
  const activeView = selectedJobId ? 'jobs' : viewByRoute[location.pathname] || 'chat'
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
  const [selectedJob, setSelectedJob] = useState(null)
  const [isLoadingSelectedJob, setIsLoadingSelectedJob] = useState(false)
  const [selectedJobError, setSelectedJobError] = useState('')
  const [profiles, setProfiles] = useState([])
  const [selectedProfileId, setSelectedProfileId] = useState(() => readStoredString(STORAGE_KEYS.selectedProfileId, null))
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(false)
  const [profilesError, setProfilesError] = useState('')
  const [hasLoadedProfiles, setHasLoadedProfiles] = useState(false)
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
    if (location.pathname === '/profiles') {
      navigate('/candidate', { replace: true })
      return
    }
    if (!viewByRoute[location.pathname] && !selectedJobIdFromPath(location.pathname)) {
      navigate('/chat', { replace: true })
    }
  }, [location.pathname, navigate])

  useEffect(() => {
    if (activeView === 'jobs' && !hasLoadedJobs && !isLoadingJobs) {
      loadJobs()
    }
  }, [activeView, hasLoadedJobs, isLoadingJobs])

  useEffect(() => {
    if (!selectedJobId) {
      setSelectedJob(null)
      setSelectedJobError('')
      return
    }

    const routeStateJob = location.state?.job && (location.state.job.id === selectedJobId || location.state.job.job_id === selectedJobId) ? location.state.job : null
    const listedJob = jobs.find((job) => job.id === selectedJobId)
    if (listedJob) {
      setSelectedJob(routeStateJob ? { ...listedJob, ...routeStateJob } : listedJob)
      setSelectedJobError('')
      return
    }

    if (routeStateJob) {
      setSelectedJob(routeStateJob)
    }

    loadSelectedJob(selectedJobId, routeStateJob)
  }, [selectedJobId, jobs, location.state])

  useEffect(() => {
    if ((activeView === 'targetProfiles' || activeView === 'matches' || activeView === 'chat') && !hasLoadedProfiles && !isLoadingProfiles) {
      loadProfiles()
    }
  }, [activeView, hasLoadedProfiles, isLoadingProfiles])

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
        target_profile_id: selectedProfileId,
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
    setIsContextPanelOpen(view === 'chat' || view === 'targetProfiles' || view === 'matches')
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

  async function loadSelectedJob(jobId = selectedJobId, contextJob = null) {
    if (!jobId) return
    setIsLoadingSelectedJob(true)
    setSelectedJobError('')
    try {
      const loadedJob = await getJob(jobId)
      setSelectedJob(contextJob ? { ...loadedJob, ...contextJob } : loadedJob)
    } catch (error) {
      setSelectedJob(null)
      setSelectedJobError(error.message)
    } finally {
      setIsLoadingSelectedJob(false)
    }
  }

  async function loadProfiles() {
    setIsLoadingProfiles(true)
    setProfilesError('')
    try {
      const loadedProfiles = await listTargetProfiles({ limit: 50 })
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

  async function loadMatches(profileId = selectedProfileId) {
    if (!profileId) return
    setIsLoadingMatches(true)
    setMatchesError('')
    try {
      const ranked = await rankJobsForTargetProfile({ targetProfileId: profileId, limit: 10 })
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
        open={(activeView === 'chat' || (activeView === 'jobs' && selectedJobId) || activeView === 'targetProfiles' || activeView === 'matches') && isContextPanelOpen}
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
          jobs={jobs}
          selectedJobId={selectedJobId}
          isLoadingJobs={isLoadingJobs}
          profiles={profiles}
          selectedProfileId={selectedProfileId}
          isLoadingProfiles={isLoadingProfiles}
          onViewChange={changeView}
          onThreadSelect={selectThread}
          onNewThread={createThread}
          onThreadRename={renameThread}
          onThreadDuplicate={duplicateThread}
          onThreadDelete={deleteThread}
          onJobsRefresh={loadJobs}
          onProfileSelect={setSelectedProfileId}
          onProfilesRefresh={loadProfiles}
        />
        <SidebarInset className="chat-root">
          <main className={activeView === 'chat' ? 'chat-page' : 'workspace-page'}>
            {activeView === 'chat' && <ChatView messages={messages} draft={draft} isSending={isSending} selectedProfile={selectedProfile} onDraftChange={setDraft} onSubmit={submitMessage} />}
            {(activeView === 'chat' || (activeView === 'jobs' && selectedJobId) || activeView === 'targetProfiles' || activeView === 'matches') && (
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
            {activeView === 'jobs' && <JobsView jobs={jobs} selectedJob={selectedJob} selectedJobId={selectedJobId} isLoading={isLoadingJobs} isLoadingSelectedJob={isLoadingSelectedJob} error={jobsError} selectedJobError={selectedJobError} onRefresh={loadJobs} onRefreshSelectedJob={() => loadSelectedJob(selectedJobId)} />}
            {activeView === 'candidate' && <CandidateView />}
            {activeView === 'settings' && <SettingsView />}
            {activeView === 'targetProfiles' && (
              <TargetProfilesView
                targetProfiles={profiles}
                selectedTargetProfileId={selectedProfileId}
                isLoading={isLoadingProfiles}
                error={profilesError}
                onSelectTargetProfile={setSelectedProfileId}
                onRefreshTargetProfiles={loadProfiles}
              />
            )}
            {activeView === 'matches' && (
              <MatchesView selectedProfile={selectedProfile} matches={rankedMatches} isLoading={isLoadingMatches} error={matchesError} onRefresh={() => selectedProfileExists && loadMatches(selectedProfileId)} onOpenProfiles={() => changeView('targetProfiles')} />
            )}
            {activeView !== 'chat' && activeView !== 'jobs' && activeView !== 'candidate' && activeView !== 'targetProfiles' && activeView !== 'matches' && activeView !== 'settings' && <PlaceholderView view={placeholderViews[activeView]} />}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}

function selectedJobIdFromPath(pathname) {
  const match = pathname.match(/^\/jobs\/([^/]+)$/)
  return match ? decodeURIComponent(match[1]) : null
}

function contextPanelToggleLabel(activeView, isOpen) {
  if (activeView === 'jobs') {
    return isOpen ? 'Hide job list' : 'Show job list'
  }
  if (activeView === 'targetProfiles' || activeView === 'matches') {
    return isOpen ? 'Hide target profile list' : 'Show target profile list'
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

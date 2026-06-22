import { WorkspaceShell } from '@/components/workspace-shell'
import { useEffect, useRef } from 'react'
import { PanelRightCloseIcon, PanelRightOpenIcon } from 'lucide-react'
import { profileName } from '../../lib/profile.js'
import { JobDetailPane } from '../jobs/JobDetailPane.jsx'
import { TailoredCVPane } from '../jobs/TailoredCVPane.jsx'
import { ChatMessage } from './ChatMessage.jsx'

export function ChatView({ messages, draft, isSending, selectedProfile, selectedJobId, selectedJob, initialLatexDraft, isJobPaneOpen, isTailoringCv, isLoadingSelectedJob, selectedJobError, onDraftChange, onSubmit, onShowJobPane, onCloseJobPane, onRefreshSelectedJob }) {
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

  const rightPane = isJobPaneOpen ? (
    <div className="chat-job-pane-content">
      <button className="chat-job-close" type="button" onClick={onCloseJobPane} aria-label="Hide workspace" title="Hide workspace">
        <PanelRightCloseIcon className="size-4" />
      </button>
      {isTailoringCv ? (
        <TailoredCVPane jobId={selectedJobId} selectedProfile={selectedProfile} initialLatexDraft={initialLatexDraft} />
      ) : (
        <JobDetailPane job={selectedJob} isLoading={isLoadingSelectedJob} error={selectedJobError} onRefresh={onRefreshSelectedJob} tailorCvBase="/chat/jobs" />
      )}
    </div>
  ) : null

  return (
    <WorkspaceShell className="chat-workspace" rightPane={rightPane} rightPaneLabel={isTailoringCv ? 'Tailored CV draft' : 'Selected job detail'} rightPaneTone={isTailoringCv ? 'draft' : 'detail'}>
      <section className="chat-panel" aria-label="Scout conversation">
        <div className="chat-conversation-column">
          <div className="transcript">
            {selectedProfile && <div className="profile-chat-chip">Matching as {profileName(selectedProfile)}</div>}
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
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
        </div>

        {selectedJobId && !isJobPaneOpen && (
          <button className="chat-job-toggle" type="button" onClick={onShowJobPane} aria-label="Show job detail" title="Show job detail">
            <PanelRightOpenIcon className="size-4" />
          </button>
        )}
      </section>
    </WorkspaceShell>
  )
}

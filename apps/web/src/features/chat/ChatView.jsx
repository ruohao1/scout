import { useEffect, useRef } from 'react'
import { PanelRightCloseIcon, PanelRightOpenIcon } from 'lucide-react'
import { profileName } from '../../lib/profile.js'
import { JobDetailPane } from '../jobs/JobDetailPane.jsx'
import { ChatMessage } from './ChatMessage.jsx'

export function ChatView({ messages, draft, isSending, selectedProfile, selectedJobId, selectedJob, isJobPaneOpen, isLoadingSelectedJob, selectedJobError, onDraftChange, onSubmit, onShowJobPane, onCloseJobPane, onRefreshSelectedJob }) {
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
    <section className={isJobPaneOpen ? 'chat-panel chat-panel-with-job' : 'chat-panel'} aria-label="Scout conversation">
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

      {isJobPaneOpen && (
        <aside className="chat-job-pane" aria-label="Selected job detail">
          <button className="chat-job-close" type="button" onClick={onCloseJobPane} aria-label="Hide job detail" title="Hide job detail">
            <PanelRightCloseIcon className="size-4" />
          </button>
          <JobDetailPane job={selectedJob} isLoading={isLoadingSelectedJob} error={selectedJobError} onRefresh={onRefreshSelectedJob} />
        </aside>
      )}
    </section>
  )
}

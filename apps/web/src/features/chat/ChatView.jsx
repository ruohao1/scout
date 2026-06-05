import { useEffect, useRef } from 'react'
import { profileName } from '../../lib/profile.js'
import { ChatMessage } from './ChatMessage.jsx'

export function ChatView({ messages, draft, isSending, selectedProfile, onDraftChange, onSubmit }) {
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

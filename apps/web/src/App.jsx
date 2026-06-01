import { useState } from 'react'
import { sendChatMessage } from './api.js'

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

function App() {
  const [messages, setMessages] = useState(initialMessages)
  const [draft, setDraft] = useState('')
  const [isSending, setIsSending] = useState(false)

  async function submitMessage(messageText = draft) {
    const content = messageText.trim()
    if (!content || isSending) return

    const userMessage = { id: crypto.randomUUID(), role: 'user', content }
    setMessages((current) => [...current, userMessage])
    setDraft('')
    setIsSending(true)

    try {
      const response = await sendChatMessage({
        message: content,
        history: messages
          .filter((message) => message.role === 'user' || message.role === 'assistant')
          .map((message) => ({ role: message.role, content: message.content })),
        profile_id: null,
        filters: {
          location: null,
          contract_type: null,
          company: null,
          seniority: null,
          remote_policy: null,
        },
        limit: 5,
      })
      setMessages((current) => [...current, assistantMessage(response)])
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `The chat endpoint did not respond: ${error.message}`,
          tool: 'none',
          jobs: [],
          rankedJobs: [],
          warnings: ['Check that the FastAPI server is running and CORS is configured.'],
        },
      ])
    } finally {
      setIsSending(false)
    }
  }

  return (
    <main className="chat-page">
      <section className="chat-panel" aria-label="Scout conversation">
        <div className="transcript">
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}
          {isSending && <p className="thinking">Scout is thinking...</p>}
        </div>

        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault()
            submitMessage()
          }}
        >
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask Scout..."
            rows="2"
          />
          <button type="submit" disabled={isSending || !draft.trim()}>
            Send
          </button>
        </form>
      </section>
    </main>
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
        <p className="evidence">{job.content}</p>
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

export default App

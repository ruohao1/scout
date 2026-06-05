import { JobCard } from '../jobs/JobCard.jsx'
import { ActivityTimeline } from './ActivityTimeline.jsx'

export function ChatMessage({ message }) {
  const results = message.rankedJobs?.length ? message.rankedJobs : message.jobs || []
  return (
    <article className={`message ${message.role}`}>
      <div className="message-meta">
        <span>{message.role === 'user' ? 'You' : 'Scout'}</span>
        {message.tool && <code>{message.tool}</code>}
      </div>
      {message.activities?.length > 0 && <ActivityTimeline activities={message.activities} status={message.status} collapsed={message.activityCollapsed} />}
      {message.content && <p>{message.content}</p>}
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

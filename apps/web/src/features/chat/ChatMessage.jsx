import { JobCard } from '../jobs/JobCard.jsx'
import { ActivityTimeline } from './ActivityTimeline.jsx'
import { MarkdownMessage } from './MarkdownMessage.jsx'

export function ChatMessage({ message }) {
  const results = message.rankedJobs?.length ? message.rankedJobs : message.jobs || []
  const activities = message.activities || []
  const hasToolActivity = activities.some((activity) => activity.kind === 'tool')
  const hasActiveOrFailedActivity = activities.some((activity) => activity.status === 'running' || activity.status === 'failed')
  const shouldShowActivity = hasToolActivity || hasActiveOrFailedActivity

  return (
    <article className={`message ${message.role}`}>
      <div className="message-meta">
        <span>{message.role === 'user' ? 'You' : 'Scout'}</span>
        {message.tool && <code>{message.tool}</code>}
      </div>
      {shouldShowActivity && <ActivityTimeline activities={activities} status={message.status} collapsed={message.activityCollapsed} />}
      {message.content && (message.role === 'assistant' ? <MarkdownMessage content={message.content} /> : <p>{message.content}</p>)}
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

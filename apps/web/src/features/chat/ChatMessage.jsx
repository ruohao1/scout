import { Link } from 'react-router-dom'
import { tailoredCvLatexPdfUrl } from '../../api.js'
import { JobCard } from '../jobs/JobCard.jsx'
import { sanitizeText } from '../../lib/sanitizeText.js'
import { ActivityTimeline } from './ActivityTimeline.jsx'
import { MarkdownMessage } from './MarkdownMessage.jsx'

export function ChatMessage({ message }) {
  const results = message.rankedJobs?.length ? message.rankedJobs : message.jobs || []
  const tailoredCvLatexArtifacts = (message.artifacts || []).filter((artifact) => artifact.type === 'tailored_cv_latex')
  const activities = message.activities || []
  const content = sanitizeText(message.content || '')
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
      {content && (message.role === 'assistant' ? <MarkdownMessage content={content} /> : <p>{content}</p>)}
      {message.warnings?.map((warning) => (
        <div className="warning" key={warning}>
          {sanitizeText(warning)}
        </div>
      ))}
      {results.length > 0 && (
        <div className="result-grid">
          {results.map((job) => (
            <JobCard key={`${job.job_id}-${job.chunk_id || 'ranked'}`} job={job} ranked={Boolean(message.rankedJobs?.length)} toBase="/chat/jobs" />
          ))}
        </div>
      )}
      {tailoredCvLatexArtifacts.length > 0 && (
        <div className="result-grid">
          {tailoredCvLatexArtifacts.map((artifact) => (
            <section className="job-card" key={`${artifact.job_id}-${artifact.artifact_id || artifact.filename || artifact.title || 'tailored-cv'}`}>
              <div className="job-card-main">
                <h3>{artifact.title || artifact.filename || 'Tailored CV LaTeX export'}</h3>
                {artifact.selected_length && <span className="job-card-meta">Length: {formatSelectedLength(artifact.selected_length)}</span>}
                {artifact.length_reason && <span className="job-card-meta">{artifact.length_reason}</span>}
                {artifact.warnings?.map((warning) => (
                  <small className="warning" key={warning}>{warning}</small>
                ))}
                <div className="tailored-cv-actions">
                  {artifact.pdf_available && artifact.artifact_id && (
                    <a href={tailoredCvLatexPdfUrl(artifact.job_id, artifact.artifact_id)} download={artifact.pdf_filename || undefined}>
                      Download PDF
                    </a>
                  )}
                  <Link to={`/chat/jobs/${artifact.job_id}/tailor-cv`} state={{ latexDraft: artifact }}>Open CV pane</Link>
                </div>
              </div>
            </section>
          ))}
        </div>
      )}
    </article>
  )
}

function formatSelectedLength(value) {
  return String(value || '').replace(/_/g, ' ')
}

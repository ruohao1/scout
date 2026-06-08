import { Link } from 'react-router-dom'
import { BanknoteIcon, BriefcaseBusinessIcon, Building2Icon, ExternalLinkIcon, FileTextIcon, MapPinIcon, RefreshCwIcon, SparklesIcon, TargetIcon } from 'lucide-react'

export function JobDetailPane({ job, isLoading, error, descriptionRefreshError, onRefresh, onRefreshDescription, isRefreshingDescription = false }) {
  if (isLoading) {
    return (
      <aside className="job-detail-pane" aria-label="Selected job details">
        <div className="job-detail-empty">
          <strong>Loading job...</strong>
          <span>Scout is opening the selected posting.</span>
        </div>
      </aside>
    )
  }

  if (error) {
    return (
      <aside className="job-detail-pane" aria-label="Selected job details">
        <div className="job-detail-empty warning-state" role="alert">
          <strong>Could not open this job.</strong>
          <span>{error}</span>
          <button type="button" onClick={onRefresh}>Try again</button>
        </div>
      </aside>
    )
  }

  if (!job) {
    return (
      <aside className="job-detail-pane" aria-label="Selected job details">
        <div className="job-detail-empty">
          <strong>Select a job</strong>
          <span>Choose a card to open the job description in this split view.</span>
        </div>
      </aside>
    )
  }

  const score = job.final_score ?? job.score
  const matchedSkills = job.matched_skills || []
  const missingSkills = job.missing_skills || []
  const description = job.description || job.content || 'No description is available for this job.'
  const jobId = job.id || job.job_id
  const hasWeakDescription = isWeakDescription(description)

  return (
    <aside className="job-detail-pane" aria-label="Selected job details">
      <div className="job-detail-scroll">
        <header className="job-detail-header">
          <div className="job-detail-kicker">
            <span>{job.source || 'Imported job'}</span>
            {typeof score === 'number' && <strong>{formatScore(score)} match</strong>}
          </div>
          <h2>{job.title}</h2>
          <dl className="job-detail-facts">
            <DetailFact icon={<Building2Icon aria-hidden="true" />} label="Company" value={job.company} />
            <DetailFact icon={<MapPinIcon aria-hidden="true" />} label="Location" value={job.location} />
            <DetailFact icon={<BriefcaseBusinessIcon aria-hidden="true" />} label="Contract" value={job.contract_type} />
            <DetailFact icon={<BanknoteIcon aria-hidden="true" />} label="Salary" value={job.salary} />
          </dl>
          <div className="job-detail-actions">
            {jobId && (
              <Link className="job-detail-link" to={`/jobs/${jobId}/tailor-cv`} state={{ job }}>
                Tailor CV bullets
                <FileTextIcon aria-hidden="true" />
              </Link>
            )}
            {jobId && hasWeakDescription && onRefreshDescription && (
              <button className="job-detail-link job-detail-action-button" type="button" onClick={onRefreshDescription} disabled={isRefreshingDescription}>
                {isRefreshingDescription ? 'Refreshing description' : 'Refresh description'}
                <RefreshCwIcon aria-hidden="true" />
              </button>
            )}
            {job.url && (
              <a className="job-detail-link" href={job.url} target="_blank" rel="noreferrer">
                Open original posting
                <ExternalLinkIcon aria-hidden="true" />
              </a>
            )}
          </div>
          {descriptionRefreshError && (
            <div className="job-detail-refresh-error warning-state" role="alert">
              {descriptionRefreshError}
            </div>
          )}
        </header>

        {(matchedSkills.length > 0 || missingSkills.length > 0 || job.evidence?.length > 0) && (
          <section className="job-detail-section">
            <h3>
              <TargetIcon aria-hidden="true" />
              Match readout
            </h3>
            <SkillLine label="Matched skills" values={matchedSkills} empty="No matched skills listed." />
            <SkillLine label="Missing skills" values={missingSkills} empty="No missing skills listed." muted />
            {job.evidence?.length > 0 && (
              <div className="job-detail-evidence">
                <span>Evidence</span>
                {job.evidence.slice(0, 2).map((item) => (
                  <blockquote key={item.chunk_id || item.content}>{item.content}</blockquote>
                ))}
              </div>
            )}
          </section>
        )}

        {job.skills?.length > 0 && (
          <section className="job-detail-section">
            <h3>
              <SparklesIcon aria-hidden="true" />
              Extracted skills
            </h3>
            <div className="tag-row">
              {job.skills.map((skill) => (
                <span key={skill}>{skill}</span>
              ))}
            </div>
          </section>
        )}

        <section className="job-detail-section">
          <h3>Description</h3>
          <div className="job-description">{descriptionParagraphs(description).map((paragraph) => <p key={paragraph}>{paragraph}</p>)}</div>
        </section>
      </div>
    </aside>
  )
}

function isWeakDescription(description) {
  return String(description || '').trim().length < 250
}

function DetailFact({ icon, label, value }) {
  if (!value) return null

  return (
    <div className="job-detail-fact">
      {icon}
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function SkillLine({ label, values, empty, muted = false }) {
  return (
    <div className="job-detail-skill-line" data-muted={muted}>
      <span>{label}</span>
      <strong>{values.length ? values.join(', ') : empty}</strong>
    </div>
  )
}

function formatScore(score) {
  const percentage = score <= 1 ? score * 100 : score
  return `${Math.round(percentage)}%`
}

function descriptionParagraphs(description) {
  return String(description)
    .replace(/\*\*/g, '')
    .split(/\n{2,}|\s\*\s+/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
    .slice(0, 28)
}

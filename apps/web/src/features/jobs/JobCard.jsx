import { BanknoteIcon, BriefcaseBusinessIcon, Building2Icon, MapPinIcon } from 'lucide-react'
import { Link } from 'react-router-dom'

export function JobCard({ job, ranked, selected = false }) {
  const jobId = job.id || job.job_id
  const score = ranked ? job.final_score : job.score
  const detail = job.salary || job.contract_type
  const detailIcon = job.salary ? <BanknoteIcon aria-hidden="true" /> : <BriefcaseBusinessIcon aria-hidden="true" />

  const card = (
    <>
      <div className="job-card-main">
        <h3>{job.title}</h3>
        <JobCardMeta icon={<Building2Icon aria-hidden="true" />} value={job.company} fallback="Company not listed" />
        <JobCardMeta icon={<MapPinIcon aria-hidden="true" />} value={job.location} fallback="Location not listed" />
        {detail && <JobCardMeta icon={detailIcon} value={detail} />}
      </div>
      {typeof score === 'number' && <span className="score">{formatScore(score)}</span>}
    </>
  )

  if (!jobId) {
    return <section className="job-card">{card}</section>
  }

  return (
    <Link className="job-card" data-selected={selected} to={`/jobs/${jobId}`} state={{ job }} aria-current={selected ? 'true' : undefined}>
      {card}
    </Link>
  )
}

function JobCardMeta({ icon, value, fallback }) {
  const text = value || fallback
  if (!text) return null

  return (
    <span className="job-card-meta">
      {icon}
      <span>{text}</span>
    </span>
  )
}

function formatScore(score) {
  const percentage = score <= 1 ? score * 100 : score
  return `${Math.round(percentage)}%`
}

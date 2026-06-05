export function JobCard({ job, ranked }) {
  const score = ranked ? job.final_score : job.score
  const content = job.content || job.description
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
        <p className="evidence">{content}</p>
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

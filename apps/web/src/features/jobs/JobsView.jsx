import { JobCard } from './JobCard.jsx'

export function JobsView({ jobs, isLoading, error, onRefresh }) {
  return (
    <section className="jobs-view" aria-label="Imported jobs">
      <header className="jobs-header">
        <div>
          <p>Jobs</p>
          <h1>Imported opportunities</h1>
          <span>{jobs.length ? `${jobs.length} postings ready for Scout search and matching.` : 'Seed jobs from the CLI, then refresh this page.'}</span>
        </div>
        <button type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </header>

      {error && (
        <div className="jobs-state warning-state" role="alert">
          <strong>Could not load jobs.</strong>
          <span>{error}</span>
          <code>uv run uvicorn apps.api.main:app --reload</code>
        </div>
      )}

      {isLoading && !jobs.length && (
        <div className="jobs-state">
          <strong>Loading jobs...</strong>
          <span>Scout is asking the API for the latest imported postings.</span>
        </div>
      )}

      {!isLoading && !error && jobs.length === 0 && (
        <div className="jobs-state">
          <strong>No jobs imported yet.</strong>
          <span>Run a mock import, then press Refresh.</span>
          <code>uv run python main.py jobs import-mock --fixture packages/services/fixtures/mock_jobs.json</code>
        </div>
      )}

      {jobs.length > 0 && (
        <div className="jobs-grid">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} ranked={false} />
          ))}
        </div>
      )}
    </section>
  )
}

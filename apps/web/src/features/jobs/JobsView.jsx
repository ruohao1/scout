import { WorkspaceShell } from '@/components/workspace-shell'
import { JobCard } from './JobCard.jsx'
import { JobDetailPane } from './JobDetailPane.jsx'
import { TailoredCVPane } from './TailoredCVPane.jsx'

export function JobsView({ jobs, selectedJob, selectedJobId, isTailoringCv, selectedProfile, isLoading, isLoadingSelectedJob, isRefreshingDescription, error, selectedJobError, descriptionRefreshError, onRefresh, onRefreshSelectedJob, onRefreshDescription }) {
  if (selectedJobId) {
    const rightPane = isTailoringCv ? <TailoredCVPane jobId={selectedJobId} selectedProfile={selectedProfile} /> : null

    return (
      <WorkspaceShell className="jobs-workspace" rightPane={rightPane} rightPaneLabel="Tailored CV draft" rightPaneTone={isTailoringCv ? 'draft' : 'neutral'}>
        <section className="jobs-view jobs-view-detail" aria-label="Selected job">
          {error && (
            <div className="jobs-state warning-state" role="alert">
              <strong>Could not load jobs.</strong>
              <span>{error}</span>
            </div>
          )}
          <JobDetailPane job={selectedJob} isLoading={isLoadingSelectedJob} error={selectedJobError} descriptionRefreshError={descriptionRefreshError} onRefresh={onRefreshSelectedJob} onRefreshDescription={onRefreshDescription} isRefreshingDescription={isRefreshingDescription} />
        </section>
      </WorkspaceShell>
    )
  }

  return (
    <section className="jobs-view" aria-label="Imported jobs">
      <header className="jobs-header">
        <div>
          <p>Jobs</p>
          <h1>Imported opportunities</h1>
          <span>{jobs.length ? `${jobs.length} postings ready for Scout search and matching.` : 'Ask Scout for latest jobs or import provider jobs, then refresh this page.'}</span>
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

      {!isLoading && !error && jobs.length === 0 && !selectedJobId && (
        <div className="jobs-state">
          <strong>No jobs imported yet.</strong>
          <span>Ask Scout for current live jobs, or import indexed Adzuna jobs from the CLI.</span>
          <code>SCOUT_EMBEDDINGS=hash uv run python main.py jobs import-adzuna --country gb --what "python developer" --where "London" --count 10</code>
        </div>
      )}

      {!selectedJobId && jobs.length > 0 && (
        <div className="jobs-grid" aria-label="Job results">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} ranked={false} />
          ))}
        </div>
      )}

    </section>
  )
}

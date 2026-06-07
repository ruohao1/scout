import { profileName } from '../../lib/profile.js'

export function MatchesView({ selectedProfile, matches, isLoading, error, onRefresh, onOpenProfiles }) {
  return (
    <section className="matches-view" aria-label="Ranked matches">
      <header className="matches-header">
        <div>
          <p>Matches</p>
          <h1>Ranked fit</h1>
          <span>{selectedProfile ? `Ranking imported jobs against ${profileName(selectedProfile)}.` : 'Select a target profile to rank imported jobs.'}</span>
        </div>
        {selectedProfile ? (
          <button type="button" onClick={onRefresh} disabled={isLoading}>
            {isLoading ? 'Ranking...' : 'Rerank jobs'}
          </button>
        ) : (
          <button type="button" onClick={onOpenProfiles}>Open target profiles</button>
        )}
      </header>

      {!selectedProfile && (
        <div className="matches-state">
          <strong>No target profile selected.</strong>
          <span>Create or select a target profile before viewing ranked matches.</span>
        </div>
      )}

      {error && (
        <div className="matches-state warning-state" role="alert">
          <strong>Could not rank jobs.</strong>
          <span>{error}</span>
        </div>
      )}

      {selectedProfile && isLoading && !matches.length && (
        <div className="matches-state">
          <strong>Ranking jobs...</strong>
          <span>Scout is comparing job evidence against the selected target profile.</span>
        </div>
      )}

      {selectedProfile && !isLoading && !error && matches.length === 0 && (
        <div className="matches-state">
          <strong>No ranked matches yet.</strong>
          <span>Import and index jobs, then run the ranking again.</span>
        </div>
      )}

      {matches.length > 0 && (
        <div className="matches-grid">
          {matches.map((match, index) => (
            <MatchCard key={match.job_id} match={match} rank={index + 1} />
          ))}
        </div>
      )}
    </section>
  )
}

function MatchCard({ match, rank }) {
  return (
    <article className="match-card">
      <div className="match-rank">#{rank}</div>
      <div className="match-card-main">
        <div className="match-card-header">
          <div>
            <h2>{match.title}</h2>
            <p>{[match.company, match.location, match.contract_type].filter(Boolean).join(' / ') || 'Unspecified'}</p>
          </div>
          <span>{match.final_score.toFixed(2)}</span>
        </div>

        <div className="match-score-grid">
          <ScorePill label="Vector" value={match.vector_score} />
          <ScorePill label="Skills" value={match.skill_overlap_score} />
          <ScorePill label="Location" value={match.location_score} />
          <ScorePill label="Contract" value={match.contract_type_score} />
        </div>

        <MatchChipGroup label="Matched skills" values={match.matched_skills} />
        <MatchChipGroup label="Missing skills" values={match.missing_skills} muted />

        {match.evidence?.length > 0 && (
          <div className="match-evidence">
            <small>Evidence</small>
            {match.evidence.slice(0, 2).map((item) => (
              <blockquote key={item.chunk_id}>{item.content}</blockquote>
            ))}
          </div>
        )}

        {match.url && (
          <a href={match.url} target="_blank" rel="noreferrer">
            Open posting
          </a>
        )}
      </div>
    </article>
  )
}

function ScorePill({ label, value }) {
  return (
    <div className="score-pill">
      <small>{label}</small>
      <strong>{typeof value === 'number' ? value.toFixed(2) : '0.00'}</strong>
    </div>
  )
}

function MatchChipGroup({ label, values = [], muted = false }) {
  if (!values.length) return null
  return (
    <div className="match-chip-group" data-muted={muted}>
      <small>{label}</small>
      <div className="tag-row">
        {values.map((value) => (
          <span key={value}>{value}</span>
        ))}
      </div>
    </div>
  )
}

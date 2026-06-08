import { useEffect, useState } from 'react'
import { AlertTriangleIcon, FileTextIcon, RefreshCwIcon, SparklesIcon } from 'lucide-react'
import { draftTailoredCv } from '../../api.js'

export function TailoredCVPane({ jobId, selectedProfile }) {
  const [instruction, setInstruction] = useState('')
  const [draft, setDraft] = useState(null)
  const [error, setError] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)

  useEffect(() => {
    setDraft(null)
    setError('')
    setInstruction('')
  }, [jobId])

  async function generateDraft() {
    if (!jobId || isGenerating) return
    setIsGenerating(true)
    setError('')
    try {
      const result = await draftTailoredCv(jobId, {
        targetProfileId: selectedProfile?.id || null,
        instruction,
        evidenceLimit: 8,
      })
      setDraft(result)
    } catch (error) {
      setError(error.message)
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <aside className="tailored-cv-pane" aria-label="Tailored CV draft">
      <div className="tailored-cv-scroll">
        <header className="tailored-cv-header">
          <p>Application draft</p>
          <h2>Tailor CV bullets</h2>
          <span>{selectedProfile ? `Using ${selectedProfile.name}` : 'Using candidate evidence without a target profile.'}</span>
        </header>

        <section className="tailored-cv-control" aria-label="Tailoring controls">
          <label>
            <span>Direction</span>
            <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Optional: emphasize backend projects, keep it junior, make bullets concise..." rows={4} />
          </label>
          <button type="button" onClick={generateDraft} disabled={isGenerating || !jobId}>
            {isGenerating ? <RefreshCwIcon aria-hidden="true" /> : <SparklesIcon aria-hidden="true" />}
            {isGenerating ? 'Drafting...' : draft ? 'Regenerate bullets' : 'Generate bullets'}
          </button>
        </section>

        {error && (
          <div className="tailored-cv-alert warning-state" role="alert">
            <AlertTriangleIcon aria-hidden="true" />
            <div>
              <strong>Could not draft CV bullets.</strong>
              <span>{error}</span>
            </div>
          </div>
        )}

        {!draft && !error && (
          <section className="tailored-cv-empty">
            <FileTextIcon aria-hidden="true" />
            <strong>Candidate RAG will choose the evidence.</strong>
            <span>Scout retrieves relevant candidate evidence for this job, then writes source-backed CV bullets you can review.</span>
          </section>
        )}

        {draft && (
          <div className="tailored-cv-result">
            <section className="tailored-cv-section">
              <p>Headline</p>
              <h3>{draft.headline}</h3>
              <span>{draft.summary}</span>
            </section>

            <section className="tailored-cv-section">
              <p>Suggested CV bullets</p>
              <ol className="tailored-cv-bullets">
                {draft.bullets.map((bullet, index) => (
                  <li key={`${bullet.text}-${index}`}>
                    <span>{bullet.text}</span>
                    {bullet.evidence_ids?.length > 0 && <small>Evidence: {bullet.evidence_ids.map(shortId).join(', ')}</small>}
                  </li>
                ))}
              </ol>
            </section>

            {draft.gaps_or_cautions?.length > 0 && (
              <section className="tailored-cv-section">
                <p>Gaps or cautions</p>
                <ul className="tailored-cv-cautions">
                  {draft.gaps_or_cautions.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </section>
            )}

            <section className="tailored-cv-section">
              <p>Evidence used</p>
              <div className="tailored-cv-evidence-list">
                {(draft.evidence_used?.length ? draft.evidence_used : draft.retrieved_evidence || []).slice(0, 6).map((item) => (
                  <article key={`${item.evidence_id}-${item.reason || item.score || ''}`} className="tailored-cv-evidence">
                    <strong>{item.title || item.type || 'Candidate evidence'}</strong>
                    <span>{[item.organization, item.location].filter(Boolean).join(' · ')}</span>
                    {item.reason && <small>{item.reason}</small>}
                  </article>
                ))}
              </div>
            </section>
          </div>
        )}
      </div>
    </aside>
  )
}

function shortId(value) {
  return String(value).slice(0, 8)
}

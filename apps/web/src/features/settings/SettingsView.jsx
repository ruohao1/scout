import { useEffect, useState } from 'react'
import { getRuntimeSettings, updateRuntimeSettings } from '../../api.js'

export function SettingsView() {
  const [settings, setSettings] = useState(null)
  const [draftSites, setDraftSites] = useState([])
  const [draftCount, setDraftCount] = useState('15')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    loadSettings()
  }, [])

  async function loadSettings() {
    setIsLoading(true)
    setError('')
    setNotice('')
    try {
      const loaded = await getRuntimeSettings()
      applySettings(loaded)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  function applySettings(nextSettings) {
    setSettings(nextSettings)
    setDraftSites(nextSettings.jobspy.sites || [])
    setDraftCount(String(nextSettings.jobspy.default_count || 15))
  }

  function toggleSite(site) {
    setNotice('')
    setDraftSites((current) => (
      current.includes(site)
        ? current.filter((item) => item !== site)
        : [...current, site]
    ))
  }

  function resetDraft() {
    if (!settings) return
    setDraftSites(settings.jobspy.sites || [])
    setDraftCount(String(settings.jobspy.default_count || 15))
    setError('')
    setNotice('Changes reset.')
  }

  async function saveSettings(event) {
    event.preventDefault()
    setError('')
    setNotice('')

    const count = Number.parseInt(draftCount, 10)
    if (!draftSites.length) {
      setError('Select at least one JobSpy site.')
      return
    }
    if (!Number.isFinite(count) || count < 1 || count > 25) {
      setError('Default live fetch count must be between 1 and 25.')
      return
    }

    setIsSaving(true)
    try {
      const saved = await updateRuntimeSettings({
        jobspy: {
          sites: draftSites,
          default_count: count,
        },
      })
      applySettings(saved)
      setNotice('Runtime settings saved.')
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSaving(false)
    }
  }

  const supportedSites = settings?.jobspy?.supported_sites || []
  const persistedKeys = settings?.persisted_keys || []

  return (
    <section className="settings-view" aria-label="Runtime settings">
      <header className="settings-hero">
        <div>
          <p>Settings</p>
          <h1>Runtime controls for live search.</h1>
          <span>Choose the JobSpy boards Scout can query. Embedding settings stay read-only because changing them requires reindexing.</span>
        </div>
        <button type="button" onClick={loadSettings} disabled={isLoading || isSaving}>{isLoading ? 'Refreshing...' : 'Refresh'}</button>
      </header>

      {error && <div className="settings-alert warning-state" role="alert"><strong>Settings action failed.</strong><span>{error}</span></div>}
      {notice && !error && <div className="settings-alert" role="status"><strong>{notice}</strong></div>}

      {isLoading && !settings && (
        <div className="jobs-state">
          <strong>Loading runtime settings...</strong>
          <span>Scout is reading persisted settings and environment defaults from the API.</span>
        </div>
      )}

      {settings && (
        <div className="settings-grid">
          <form className="settings-panel settings-panel-primary" onSubmit={saveSettings}>
            <div className="settings-panel-heading">
              <p>JobSpy</p>
              <h2>Live job sources</h2>
              <span>Saved here, then used by chat live-search and JobSpy import runs.</span>
            </div>

            <div className="settings-site-grid">
              {supportedSites.map((site) => (
                <label key={site} className="settings-site-option">
                  <input type="checkbox" checked={draftSites.includes(site)} onChange={() => toggleSite(site)} />
                  <span>{siteLabel(site)}</span>
                </label>
              ))}
            </div>

            <label className="settings-count-field">
              Default live fetch count
              <input type="number" min="1" max="25" value={draftCount} onChange={(event) => { setDraftCount(event.target.value); setNotice('') }} />
              <span>Bounded to 1-25 jobs per live fetch to keep search responsive.</span>
            </label>

            <div className="settings-actions">
              <button type="submit" disabled={isSaving || isLoading}>{isSaving ? 'Saving...' : 'Save settings'}</button>
              <button type="button" onClick={resetDraft} disabled={isSaving}>Reset</button>
            </div>
          </form>

          <aside className="settings-panel settings-facts">
            <RuntimeFact title="Active sites" value={settings.jobspy.sites.map(siteLabel).join(', ')} />
            <RuntimeFact title="Default sites" value={settings.jobspy.default_sites.map(siteLabel).join(', ')} />
            <RuntimeFact title="Environment sites" value={settings.jobspy.env_sites.map(siteLabel).join(', ')} />
            <RuntimeFact title="Persisted keys" value={persistedKeys.length ? persistedKeys.join(', ') : 'None'} />
          </aside>

          <aside className="settings-panel settings-facts">
            <div className="settings-panel-heading compact">
              <p>Read-only</p>
              <h2>Embeddings and runtime</h2>
            </div>
            <RuntimeFact title="Embedding provider" value={settings.embeddings.provider} />
            <RuntimeFact title="Embedding dimensions" value={settings.embeddings.dimensions} />
            <RuntimeFact title="Gemini model" value={settings.embeddings.gemini_model} />
            <RuntimeFact title="OpenAI model" value={settings.embeddings.openai_model} />
            <RuntimeFact title="Database" value={settings.runtime.database} />
            <RuntimeFact title="Auth directory" value={settings.runtime.auth_dir} />
          </aside>
        </div>
      )}
    </section>
  )
}

function RuntimeFact({ title, value }) {
  return (
    <div className="settings-fact">
      <span>{title}</span>
      <strong>{value || 'Not set'}</strong>
    </div>
  )
}

function siteLabel(site) {
  return site.replaceAll('_', ' ')
}

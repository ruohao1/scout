import { useEffect, useState } from 'react'
import { sanitizeText } from '../../lib/sanitizeText.js'
import { formatActivityArgs } from './chatStreamReducer.js'

export function ActivityTimeline({ activities, status, collapsed }) {
  const [isCollapsed, setIsCollapsed] = useState(Boolean(collapsed))
  const tools = activities.filter((activity) => activity.kind === 'tool')
  const toolCount = tools.length
  const toolLabel = toolCount === 1 ? `Used ${tools[0].title}` : `Used ${toolCount} tools`
  const hasRunning = status === 'running' || activities.some((activity) => activity.status === 'running')

  useEffect(() => {
    setIsCollapsed(Boolean(collapsed))
  }, [collapsed])

  return (
    <div className="activity-card" data-running={hasRunning} data-expanded={!isCollapsed}>
      <button className="activity-summary" type="button" onClick={() => setIsCollapsed((current) => !current)} aria-expanded={!isCollapsed}>
        <span className="activity-pulse" data-status={hasRunning ? 'running' : status || 'completed'} />
        <strong>{sanitizeText(hasRunning ? 'Working' : toolLabel)}</strong>
        <small>{isCollapsed ? 'Show trace' : 'Hide'}</small>
      </button>

      {!isCollapsed && (
        <div className="activity-list">
          {activities.map((activity) => (
            <ActivityRow key={`${activity.kind}-${activity.id}`} activity={activity} />
          ))}
        </div>
      )}
    </div>
  )
}

function ActivityRow({ activity }) {
  return (
    <div className="activity-row" data-kind={activity.kind} data-status={activity.status}>
      <span className="activity-marker" aria-hidden="true" />
      <div>
        <div className="activity-row-title">
          <strong>{sanitizeText(activity.title)}</strong>
          <small>{activity.kind}</small>
        </div>
        {activity.args && <code>{sanitizeText(formatActivityArgs(activity.args))}</code>}
        {activity.summary && <p>{sanitizeText(activity.summary)}</p>}
      </div>
    </div>
  )
}

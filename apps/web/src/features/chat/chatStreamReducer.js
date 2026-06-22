import { sanitizeText } from '../../lib/sanitizeText.js'

export function applyChatStreamEvent(thread, assistantId, event) {
  if (event.type === 'done') {
    const response = event.response || {}
    return {
      ...thread,
      detail: sanitizeText(response.message || 'Scout finished.'),
      messages: thread.messages.map((message) =>
        message.id === assistantId
          ? {
              ...message,
              content: sanitizeText(response.message || ''),
              tool: response.tool || 'none',
              jobs: response.jobs || [],
              rankedJobs: response.ranked_jobs || [],
              artifacts: response.artifacts || [],
              warnings: (response.warnings || []).map((warning) => sanitizeText(warning)),
              status: 'completed',
              activityCollapsed: true,
              activities: completeRunningActivities(message.activities || []),
            }
          : message,
      ),
    }
  }

  if (event.type === 'error') {
    return {
      ...thread,
      detail: 'The chat stream failed.',
      messages: thread.messages.map((message) =>
        message.id === assistantId
          ? {
              ...message,
              content: sanitizeText(event.message || 'The chat stream failed.'),
              status: 'failed',
              activityCollapsed: false,
              activities: failRunningActivities(message.activities || [], sanitizeText(event.message || 'Stream failed')),
            }
          : message,
      ),
    }
  }

  return {
    ...thread,
    messages: thread.messages.map((message) =>
      message.id === assistantId
        ? {
            ...message,
            activities: applyActivityEvent(message.activities || [], event),
          }
        : message,
    ),
  }
}

function applyActivityEvent(activities, event) {
  if (event.type?.startsWith('step_')) {
    const status = event.type === 'step_started' ? 'running' : event.type === 'step_failed' ? 'failed' : 'completed'
    return upsertActivity(activities, {
      id: event.id,
      kind: 'step',
      title: event.title || activityTitle(event.id),
      summary: event.summary || '',
      status,
    })
  }

  if (event.type?.startsWith('tool_')) {
    const status = event.type === 'tool_started' ? 'running' : event.type === 'tool_failed' ? 'failed' : 'completed'
    return upsertActivity(activities, {
      id: event.id,
      kind: 'tool',
      title: event.tool || event.id,
      args: event.args || null,
      summary: event.summary || '',
      status,
    })
  }

  return activities
}

function upsertActivity(activities, next) {
  const index = activities.findIndex((activity) => activity.id === next.id && activity.kind === next.kind)
  if (index === -1) return [...activities, next]
  return activities.map((activity, currentIndex) => (currentIndex === index ? { ...activity, ...next } : activity))
}

function completeRunningActivities(activities) {
  return activities.map((activity) => (activity.status === 'running' ? { ...activity, status: 'completed' } : activity))
}

export function failRunningActivities(activities, summary) {
  if (!activities.length) {
    return [{ id: 'stream', kind: 'step', title: 'Connect to Scout', status: 'failed', summary }]
  }
  return activities.map((activity) => (activity.status === 'running' ? { ...activity, status: 'failed', summary } : activity))
}

function activityTitle(id) {
  return String(id || 'step')
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export function formatActivityArgs(args) {
  const entries = Object.entries(args).filter(([, value]) => value !== null && value !== undefined && value !== '')
  if (!entries.length) return '{}'
  return entries
    .map(([key, value]) => `${key}=${typeof value === 'object' ? JSON.stringify(value) : JSON.stringify(value)}`)
    .join(' ')
}

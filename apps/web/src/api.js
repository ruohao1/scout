const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export async function sendChatMessage(payload) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Chat request failed with HTTP ${response.status}`)
  }

  return response.json()
}

export async function sendChatMessageStream(payload, onEvent) {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Chat stream failed with HTTP ${response.status}`)
  }

  if (!response.body) {
    throw new Error('Chat stream did not return a readable body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''
    for (const eventText of events) {
      const dataLine = eventText.split('\n').find((line) => line.startsWith('data: '))
      if (!dataLine) continue
      onEvent(JSON.parse(dataLine.slice(6)))
    }
  }

  if (buffer.trim()) {
    const dataLine = buffer.split('\n').find((line) => line.startsWith('data: '))
    if (dataLine) {
      onEvent(JSON.parse(dataLine.slice(6)))
    }
  }
}

export async function listJobs({ limit = 50 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  const response = await fetch(`${API_BASE_URL}/jobs?${params.toString()}`)

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Jobs request failed with HTTP ${response.status}`)
  }

  return response.json()
}

export async function listProfiles({ limit = 50 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  const response = await fetch(`${API_BASE_URL}/profiles?${params.toString()}`)

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Profiles request failed with HTTP ${response.status}`)
  }

  return response.json()
}

export async function createProfile(profile) {
  const response = await fetch(`${API_BASE_URL}/profiles`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(profile),
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Profile create failed with HTTP ${response.status}`)
  }

  return response.json()
}

export async function uploadProfile(formData) {
  const response = await fetch(`${API_BASE_URL}/profiles/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Profile upload failed with HTTP ${response.status}`)
  }

  return response.json()
}

export async function rankJobsForProfile({ profileId, filters, limit = 10 }) {
  const response = await fetch(`${API_BASE_URL}/rank-jobs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      profile_id: profileId,
      filters: filters || {
        location: null,
        contract_type: null,
        company: null,
        seniority: null,
        remote_policy: null,
      },
      limit,
    }),
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Rank jobs request failed with HTTP ${response.status}`)
  }

  return response.json()
}

export { API_BASE_URL }

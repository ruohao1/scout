const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const PROFILE_UPLOAD_TIMEOUT_MS = 90_000

export async function sendChatMessage(payload) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Chat request failed with HTTP ${response.status}`))
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
    throw new Error(await errorMessage(response, `Chat stream failed with HTTP ${response.status}`))
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
    throw new Error(await errorMessage(response, `Jobs request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function listProfiles({ limit = 50 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  const response = await fetch(`${API_BASE_URL}/profiles?${params.toString()}`)

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Profiles request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function getProfile(profileId) {
  const response = await fetch(`${API_BASE_URL}/profiles/${profileId}`)

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Profile request failed with HTTP ${response.status}`))
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
    throw new Error(await errorMessage(response, `Profile create failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function uploadProfile(formData) {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), PROFILE_UPLOAD_TIMEOUT_MS)
  let response
  try {
    response = await fetch(`${API_BASE_URL}/profiles/upload`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Profile upload timed out. Try again with AI extraction disabled.')
    }
    throw error
  } finally {
    window.clearTimeout(timeoutId)
  }

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Profile upload failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function attachProfileCv(profileId, formData) {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), PROFILE_UPLOAD_TIMEOUT_MS)
  let response
  try {
    response = await fetch(`${API_BASE_URL}/profiles/${profileId}/cv`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('CV upload timed out. Try a smaller PDF.')
    }
    throw error
  } finally {
    window.clearTimeout(timeoutId)
  }

  if (!response.ok) {
    throw new Error(await errorMessage(response, `CV upload failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function getProfileEnrichment(profileId) {
  const response = await fetch(`${API_BASE_URL}/profiles/${profileId}/enrichment`)

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Profile enrichment request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export function profileCvUrl(profileId) {
  return `${API_BASE_URL}/profiles/${profileId}/cv`
}

export async function getCandidate() {
  const response = await fetch(`${API_BASE_URL}/candidate`)

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Candidate request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function updateCandidate(candidate) {
  return jsonRequest('/candidate', 'PUT', candidate, 'Candidate update failed')
}

export async function listCandidateDocuments({ limit = 50 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  const response = await fetch(`${API_BASE_URL}/candidate/documents?${params.toString()}`)

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Candidate documents request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function uploadCandidateDocument(formData) {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), PROFILE_UPLOAD_TIMEOUT_MS)
  let response
  try {
    response = await fetch(`${API_BASE_URL}/candidate/documents/upload`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Candidate document upload timed out. Try a smaller PDF or disable AI extraction.')
    }
    throw error
  } finally {
    window.clearTimeout(timeoutId)
  }

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Candidate document upload failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function listCandidateEvidence({ type = null, limit = 200 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (type) params.set('type', type)
  const response = await fetch(`${API_BASE_URL}/candidate/evidence?${params.toString()}`)

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Candidate evidence request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function createCandidateEvidence(evidence) {
  return jsonRequest('/candidate/evidence', 'POST', evidence, 'Candidate evidence create failed')
}

export async function updateCandidateEvidence(evidenceId, evidence) {
  return jsonRequest(`/candidate/evidence/${evidenceId}`, 'PUT', evidence, 'Candidate evidence update failed')
}

export async function deleteCandidateEvidence(evidenceId) {
  await deleteRequest(`/candidate/evidence/${evidenceId}`, 'Candidate evidence delete failed')
}

export async function reindexCandidateEvidence() {
  return jsonRequest('/candidate/evidence/reindex', 'POST', {}, 'Candidate evidence reindex failed')
}

export async function listTargetProfiles({ limit = 50 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  const response = await fetch(`${API_BASE_URL}/target-profiles?${params.toString()}`)

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Target profiles request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function createTargetProfile(profile) {
  return jsonRequest('/target-profiles', 'POST', profile, 'Target profile create failed')
}

export async function getTargetProfile(targetProfileId) {
  const response = await fetch(`${API_BASE_URL}/target-profiles/${targetProfileId}`)

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Target profile request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function updateTargetProfile(targetProfileId, profile) {
  return jsonRequest(`/target-profiles/${targetProfileId}`, 'PUT', profile, 'Target profile update failed')
}

export async function deleteTargetProfile(targetProfileId) {
  await deleteRequest(`/target-profiles/${targetProfileId}`, 'Target profile delete failed')
}

export async function suggestTargetProfiles({ count = 3 } = {}) {
  return jsonRequest('/target-profiles/suggest', 'POST', { count }, 'Target profile suggestion failed')
}

export async function createProfileExperience(profileId, experience) {
  return profileJsonRequest(`/profiles/${profileId}/experiences`, 'POST', experience, 'Profile experience create failed')
}

export async function updateProfileExperience(profileId, experienceId, experience) {
  return profileJsonRequest(`/profiles/${profileId}/experiences/${experienceId}`, 'PUT', experience, 'Profile experience update failed')
}

export async function deleteProfileExperience(profileId, experienceId) {
  await profileDeleteRequest(`/profiles/${profileId}/experiences/${experienceId}`, 'Profile experience delete failed')
}

export async function createProfileProject(profileId, project) {
  return profileJsonRequest(`/profiles/${profileId}/projects`, 'POST', project, 'Profile project create failed')
}

export async function updateProfileProject(profileId, projectId, project) {
  return profileJsonRequest(`/profiles/${profileId}/projects/${projectId}`, 'PUT', project, 'Profile project update failed')
}

export async function deleteProfileProject(profileId, projectId) {
  await profileDeleteRequest(`/profiles/${profileId}/projects/${projectId}`, 'Profile project delete failed')
}

export async function createProfileSkill(profileId, skill) {
  return profileJsonRequest(`/profiles/${profileId}/skills`, 'POST', skill, 'Profile skill create failed')
}

export async function updateProfileSkill(profileId, skillId, skill) {
  return profileJsonRequest(`/profiles/${profileId}/skills/${skillId}`, 'PUT', skill, 'Profile skill update failed')
}

export async function deleteProfileSkill(profileId, skillId) {
  await profileDeleteRequest(`/profiles/${profileId}/skills/${skillId}`, 'Profile skill delete failed')
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
    throw new Error(await errorMessage(response, `Rank jobs request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function rankJobsForTargetProfile({ targetProfileId, filters, limit = 10 }) {
  const response = await fetch(`${API_BASE_URL}/rank-jobs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      target_profile_id: targetProfileId,
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
    throw new Error(await errorMessage(response, `Rank jobs request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function getRuntimeSettings() {
  const response = await fetch(`${API_BASE_URL}/settings/runtime`)

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Settings request failed with HTTP ${response.status}`))
  }

  return response.json()
}

export async function updateRuntimeSettings(settings) {
  return jsonRequest('/settings/runtime', 'PUT', settings, 'Settings update failed')
}

export { API_BASE_URL }

async function errorMessage(response, fallback) {
  const text = await response.text()
  if (!text) return fallback
  try {
    const data = JSON.parse(text)
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg || item.message || JSON.stringify(item)).join('; ')
    }
  } catch {
    return text
  }
  return text
}

async function profileJsonRequest(path, method, payload, fallback) {
  return jsonRequest(path, method, payload, fallback)
}

async function jsonRequest(path, method, payload, fallback) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(await errorMessage(response, `${fallback} with HTTP ${response.status}`))
  }

  return response.json()
}

async function profileDeleteRequest(path, fallback) {
  return deleteRequest(path, fallback)
}

async function deleteRequest(path, fallback) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error(await errorMessage(response, `${fallback} with HTTP ${response.status}`))
  }
}

export const ACTIVE_TARGET_PROFILE_ID_KEY = 'scout.activeTargetProfileId'

export function readStoredJson(key, fallback) {
  try {
    const value = window.localStorage.getItem(key)
    return value ? JSON.parse(value) : fallback
  } catch {
    return fallback
  }
}

export function writeStoredJson(key, value) {
  window.localStorage.setItem(key, JSON.stringify(value))
}

export function readStoredString(key, fallback = null) {
  return window.localStorage.getItem(key) || fallback
}

export function writeStoredString(key, value) {
  if (value) {
    window.localStorage.setItem(key, value)
  } else {
    window.localStorage.removeItem(key)
  }
}

export function readStoredBoolean(key, fallback) {
  const value = window.localStorage.getItem(key)
  if (value === 'true') return true
  if (value === 'false') return false
  return fallback
}

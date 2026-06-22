export function sanitizeText(value) {
  if (typeof value !== 'string') return value
  return value.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/gi, ' ').replace(/\s+/g, ' ').trim()
}

export function sanitizeObject(value) {
  if (typeof value === 'string') return sanitizeText(value)
  if (Array.isArray(value)) return value.map((item) => sanitizeObject(item))
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, sanitizeObject(item)]))
  }
  return value
}

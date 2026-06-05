export function csvValues(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function blankToNull(value) {
  const trimmed = value.trim()
  return trimmed || null
}

export function profileName(profile) {
  return profile.name || profile.target_roles?.[0] || 'Candidate profile'
}

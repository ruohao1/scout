# Candidate Dossier UI Design

## Goal

Redesign Scout's candidate/profile area into a polished candidate knowledge dossier, while moving target-profile management into a separate route.

## Product Boundaries

Scout has four distinct user-facing areas:

- `/onboarding`: fast setup flow for CV upload, extraction review, and first target-profile creation. This is separate from the long-term Candidate route and can be built later.
- `/candidate`: base candidate knowledge only. This is the durable evidence database presented as a polished resume dossier.
- `/target-profiles`: job-search personas, preferences, selected candidate evidence, evidence weights, and keywords.
- `/matches`: ranked jobs for the active target profile, explanations, gaps, and match review.

The Candidate route must not include target profile editing, evidence weights, matching controls, ranking actions, or job preferences.

## Candidate Route

The Candidate route should feel like a refined resume dossier rather than a dense admin table. Its primary job is to answer: what do we know about this person, where did that knowledge come from, and how ready is it for downstream matching?

### Layout

- A dossier hero header shows candidate name, headline, summary, document status, evidence count, and review status.
- A top action row provides `Add evidence`, `Upload document`, `Review low-confidence`, and `Search candidate knowledge`.
- The main content is a single polished narrative column grouped by evidence type.
- Evidence editing opens in a right-side inspector or slide-over so the dossier remains readable.
- The page remains usable on mobile by stacking the hero, actions, sections, and editor drawer.

### Sections

Candidate evidence is grouped into these sections in stable order:

- Experience
- Projects
- Skills
- Education
- Certifications
- Languages
- Interests
- Document notes

Empty sections should be compact and helpful, not visually dominant. Sections with evidence should show curated cards, not rows.

### Evidence Cards

Each evidence card should show:

- Title
- Organization or context when present
- Date range and location when present
- Description or proof points
- Skills/tags
- Source document indicator when present
- Confidence or review state when useful

Cards should make extracted evidence feel trustworthy but editable. Low-confidence or source-less evidence should be visibly reviewable without looking like an error state.

### Editing

Editing should happen through a focused inspector or slide-over with fields for:

- Evidence type
- Title
- Organization/context
- Location
- Date range/current flag
- Description
- Skills/tags
- URL
- Source document
- Confidence/review metadata when available

Saving an evidence item should refresh the dossier section without moving the user away from their current context. Deleting evidence should be available but visually secondary.

### Documents

Documents are candidate source material, not target profiles. The Candidate route should show uploaded documents/CVs, extraction status where available, and latest source information. Uploading a document can extract candidate evidence, but it should not create or edit target profiles from this route.

## Target Profiles Route

Target profiles need their own dedicated route because they are job-search personas, not base candidate knowledge.

The route should include:

- Target profile list
- Target profile editor
- Roles, locations, contracts, seniority, and remote preference
- Must-have, nice-to-have, and avoid keywords
- Candidate evidence picker
- Evidence weights from `0` to `1`
- AI suggestion flow that returns unsaved drafts and requires explicit save

The Target Profiles route is allowed to reference candidate evidence and weight it. The Candidate route is not allowed to show or edit weights.

## Navigation

Visible navigation should no longer present the candidate knowledge workspace as `Profiles`. Preferred labels:

- `Candidate` for `/candidate`
- `Target Profiles` for `/target-profiles`
- `Matches` for ranked jobs
- `Chat` and `Jobs` unchanged

If route renaming creates too much implementation churn, paths can remain temporarily compatible internally, but visible UI copy should reflect Candidate and Target Profiles.

## Existing Code Impact

Current relevant files:

- `apps/web/src/features/profiles/ProfilesView.jsx` currently mixes candidate evidence and target-profile editing.
- `apps/web/src/App.jsx` currently uses `profiles` state for target profiles and routes `/profiles` to `ProfilesView`.
- `apps/web/src/components/app-sidebar.jsx` currently renders a context panel for target profiles under profile naming.
- `apps/web/src/api.js` already contains candidate and target-profile API client functions.
- `apps/web/src/styles.css` already contains candidate/profile styles that can be reused but should be cleaned up around the new route split.

The redesign should split responsibilities rather than adding more conditional UI to the existing mixed component.

## Success Criteria

- The Candidate route contains only base candidate knowledge.
- The Target Profiles route owns target profile preferences, selected evidence, and weights.
- The Candidate route feels like a polished dossier with grouped resume-like sections.
- Evidence remains easy to add, edit, delete, search, and review.
- The web build passes with `pnpm run build`.

## Out Of Scope

- Building the full onboarding flow in this pass.
- Changing backend candidate or target-profile APIs unless a small frontend-enabling adjustment is required.
- Redesigning Matches beyond updating it to point users at Target Profiles when no active target profile is selected.
- Removing legacy backend `/profiles` endpoints.

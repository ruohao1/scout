# Candidate Dossier UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Candidate and Target Profiles into separate frontend routes, making Candidate a polished base-knowledge dossier and Target Profiles the persona/evidence-weighting workspace.

**Architecture:** Keep existing backend APIs and API client functions. Split the current mixed `ProfilesView` into focused frontend views: Candidate owns identity/documents/evidence; Target Profiles owns personas, preferences, selected evidence, weights, and AI drafts. Update routing, sidebar labels, and Matches copy to use active target profiles.

**Tech Stack:** Vite, React 19, React Router, existing CSS design system in `apps/web/src/styles.css`, existing FastAPI endpoints through `apps/web/src/api.js`, pnpm.

---

## File Structure

- Create `apps/web/src/features/candidate/CandidateView.jsx`: candidate base knowledge dossier, document upload, grouped evidence cards, and evidence editor drawer.
- Create `apps/web/src/features/target-profiles/TargetProfilesView.jsx`: target profile list, editor, evidence picker/weights, and AI suggestions.
- Modify `apps/web/src/App.jsx`: add `/candidate` and `/target-profiles` routes, load target profiles for chat/matches/sidebar, remove legacy mixed profile view wiring.
- Modify `apps/web/src/components/app-sidebar.jsx`: show `Candidate` and `Target Profiles` navigation entries; keep context panel focused on target profiles when relevant.
- Modify `apps/web/src/features/matches/MatchesView.jsx`: update empty/selected copy to point at target profiles.
- Modify `apps/web/src/lib/profile.js`: add or keep naming helpers for target profiles without candidate ambiguity.
- Modify `apps/web/src/styles.css`: add dossier layout, evidence card, editor drawer, and target profile workspace styles; remove or stop depending on mixed profile-specific layout where practical.

## Task 1: Route Split And Navigation

**Files:**
- Modify: `apps/web/src/App.jsx`
- Modify: `apps/web/src/components/app-sidebar.jsx`
- Modify: `apps/web/src/features/matches/MatchesView.jsx`

- [ ] **Step 1: Add route names**

In `apps/web/src/App.jsx`, change `routeByView` to include:

```javascript
const routeByView = {
  chat: '/chat',
  jobs: '/jobs',
  matches: '/matches',
  candidate: '/candidate',
  targetProfiles: '/target-profiles',
  settings: '/settings',
}
```

Keep `/profiles` as a temporary redirect target by mapping unknown route handling to `/candidate` only if needed after imports compile.

- [ ] **Step 2: Update sidebar nav**

In `apps/web/src/components/app-sidebar.jsx`, set primary nav items to:

```javascript
const navItems = [
  { id: "chat", title: "Chat", path: "/chat", icon: <BotIcon /> },
  { id: "jobs", title: "Jobs", path: "/jobs", icon: <BriefcaseBusinessIcon /> },
  { id: "candidate", title: "Candidate", path: "/candidate", icon: <UserRoundIcon /> },
  { id: "targetProfiles", title: "Target Profiles", path: "/target-profiles", icon: <TargetIcon /> },
  { id: "matches", title: "Matches", path: "/matches", icon: <TargetIcon /> },
  { id: "settings", title: "Settings", path: "/settings", icon: <Settings2Icon /> },
]
```

The context panel should remain for `chat`, `targetProfiles`, and `matches`, and it should list target profiles, not candidate knowledge.

- [ ] **Step 3: Update matches language**

Ensure `apps/web/src/features/matches/MatchesView.jsx` uses `target profile` in selected and empty states.

- [ ] **Step 4: Build check**

Run: `pnpm run build` from `apps/web`.

Expected: build exits `0`; Vite large chunk warning is acceptable.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/App.jsx apps/web/src/components/app-sidebar.jsx apps/web/src/features/matches/MatchesView.jsx
git commit -m "feat: split candidate and target profile routes"
```

## Task 2: Candidate Dossier View

**Files:**
- Create: `apps/web/src/features/candidate/CandidateView.jsx`
- Modify: `apps/web/src/App.jsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Create CandidateView state and data loading**

Create `CandidateView.jsx` that imports `getCandidate`, `updateCandidate`, `listCandidateDocuments`, `uploadCandidateDocument`, `listCandidateEvidence`, `createCandidateEvidence`, `updateCandidateEvidence`, and `deleteCandidateEvidence` from `../../api.js`.

Load candidate, documents, and evidence with `Promise.allSettled`. Treat `Candidate not found` as an empty candidate state; show other errors in a warning block.

- [ ] **Step 2: Implement dossier hero**

Render a hero with candidate display name, headline, summary, latest document, evidence count, and low-confidence count. Actions: `Add evidence`, `Upload document`, `Review low-confidence`, and search input.

- [ ] **Step 3: Implement grouped sections**

Group evidence by stable types:

```javascript
const EVIDENCE_TYPES = [
  ['experience', 'Experience'],
  ['project', 'Projects'],
  ['skill', 'Skills'],
  ['education', 'Education'],
  ['certification', 'Certifications'],
  ['language', 'Languages'],
  ['interest', 'Interests'],
  ['document_note', 'Document notes'],
]
```

Render polished cards for each evidence item. Empty sections should be compact.

- [ ] **Step 4: Implement editor drawer**

Clicking `Add evidence` or an evidence card opens a right-side editor drawer. Fields: type, title, organization, location, dates/current, description, skills, url, confidence. Save calls create/update API and refreshes evidence. Delete is secondary.

- [ ] **Step 5: Wire route**

In `App.jsx`, render `<CandidateView />` for `activeView === 'candidate'`.

- [ ] **Step 6: Build check**

Run: `pnpm run build` from `apps/web`.

Expected: build exits `0`; Vite large chunk warning is acceptable.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/features/candidate/CandidateView.jsx apps/web/src/App.jsx apps/web/src/styles.css
git commit -m "feat: add candidate dossier view"
```

## Task 3: Target Profiles View

**Files:**
- Create: `apps/web/src/features/target-profiles/TargetProfilesView.jsx`
- Modify: `apps/web/src/App.jsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Move target profile UI**

Create `TargetProfilesView.jsx` using existing API functions: `listCandidateEvidence`, `createTargetProfile`, `updateTargetProfile`, `deleteTargetProfile`, and `suggestTargetProfiles`.

Props from App: `targetProfiles`, `selectedTargetProfileId`, `isLoading`, `error`, `onSelectTargetProfile`, and `onRefreshTargetProfiles`.

- [ ] **Step 2: Implement target profile editor**

Editor fields: name, summary, roles, locations, contracts, seniority, remote preference, must-have keywords, nice-to-have keywords, avoid keywords, instructions.

- [ ] **Step 3: Implement evidence picker and weights**

Show candidate evidence as compact selectable cards. Selected evidence gets numeric weight input with `min="0"`, `max="1"`, and `step="0.1"`. This route owns evidence weights.

- [ ] **Step 4: Implement AI drafts**

`Suggest target profiles` calls `suggestTargetProfiles({ count: 3 })`, shows unsaved draft cards, and saves only when the user clicks `Save draft`.

- [ ] **Step 5: Wire route**

In `App.jsx`, render `<TargetProfilesView />` for `activeView === 'targetProfiles'`.

- [ ] **Step 6: Build check**

Run: `pnpm run build` from `apps/web`.

Expected: build exits `0`; Vite large chunk warning is acceptable.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/features/target-profiles/TargetProfilesView.jsx apps/web/src/App.jsx apps/web/src/styles.css
git commit -m "feat: add target profiles workspace"
```

## Task 4: Cleanup Legacy Mixed Profiles View

**Files:**
- Delete or stop importing: `apps/web/src/features/profiles/ProfilesView.jsx`
- Modify: `apps/web/src/App.jsx`
- Modify: `apps/web/src/components/app-sidebar.jsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Remove mixed view imports and dead handlers**

Remove imports and state/functions used only by legacy `/profiles` UI: legacy profile create/upload/enrichment actions if no remaining component uses them.

- [ ] **Step 2: Redirect `/profiles`**

If a user navigates to `/profiles`, route them to `/candidate` with replace navigation.

- [ ] **Step 3: Remove or leave harmless CSS**

Remove obviously unused mixed-profile CSS if easy. If removal risks churn, leave harmless styles for a later cleanup.

- [ ] **Step 4: Build check**

Run: `pnpm run build` from `apps/web`.

Expected: build exits `0`; Vite large chunk warning is acceptable.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/App.jsx apps/web/src/components/app-sidebar.jsx apps/web/src/styles.css apps/web/src/features/profiles/ProfilesView.jsx
git commit -m "chore: remove mixed profiles workspace"
```

If `ProfilesView.jsx` is deleted, use `git rm apps/web/src/features/profiles/ProfilesView.jsx`.

## Task 5: Final Verification

**Files:**
- Modify: `AGENTS.md` only if command guidance changes.

- [ ] **Step 1: Run web build**

Run: `pnpm run build` from `apps/web`.

Expected: build exits `0`; Vite large chunk warning is acceptable.

- [ ] **Step 2: Run Python compile smoke**

Run: `uv run python -m compileall main.py apps packages` from repo root.

Expected: command exits `0`.

- [ ] **Step 3: Inspect final status**

Run: `git status --short`.

Expected: no unintended changes except known untracked local config files such as `opencode.json` or `.superpowers/`.

- [ ] **Step 4: Commit any doc/guidance cleanup**

If `AGENTS.md` changes:

```bash
git add AGENTS.md
git commit -m "docs: update candidate ui guidance"
```

If no docs change is needed, do not create an empty commit.

## Self-Review

- Spec coverage: Candidate-only base knowledge, separate Target Profiles route, navigation split, dossier sections, editor drawer, and build verification are covered.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: `targetProfiles`, `selectedTargetProfileId`, candidate evidence fields, and route ids are used consistently.

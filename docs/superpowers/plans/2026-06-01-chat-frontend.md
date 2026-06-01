# Chat Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-orchestrated chat UI for Scout that searches jobs and ranks jobs for a selected candidate profile.

**Architecture:** Add a deterministic `services.chat` layer and `POST /chat` FastAPI route that select a limited tool (`search_jobs` or `rank_jobs_for_profile`) and return structured results. Add a new React + Vite app in `apps/web` that renders a chat transcript, profile/filter controls, and job result cards.

**Tech Stack:** Python 3.13, FastAPI, uv workspace packages, React, Vite, CSS.

---

### Task 1: Backend Chat API

**Files:**
- Modify: `apps/api/schemas.py`
- Create: `packages/services/src/services/chat.py`
- Modify: `packages/services/src/services/__init__.py`
- Create: `apps/api/routes/chat.py`
- Modify: `apps/api/main.py`

- [ ] Add Pydantic request/response models for chat messages, filters, tool names, and structured result payloads.
- [ ] Implement deterministic search and match intent routing in `services.chat`.
- [ ] Add `POST /chat` as a thin FastAPI adapter.
- [ ] Enable CORS for local Vite development.

### Task 2: React App Scaffold

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.jsx`
- Create: `apps/web/src/api.js`
- Create: `apps/web/src/App.jsx`
- Create: `apps/web/src/styles.css`

- [ ] Scaffold a Vite React app with no router and no heavy state library.
- [ ] Implement a chat API client using `VITE_API_BASE_URL` with a `http://127.0.0.1:8000` fallback.
- [ ] Build a distinctive, responsive chat workbench UI with transcript, controls, composer, and result cards.

### Task 3: Verification

**Commands:**
- `uv run python -m compileall apps/api packages/services/src/services`
- `uv run python -c 'from apps.api.main import app; print(app.title)'`
- `uv run python -c 'from services.chat import respond_to_chat; print(respond_to_chat(message="find Python jobs", limit=1).message)'`
- `npm install` in `apps/web`
- `npm run build` in `apps/web`

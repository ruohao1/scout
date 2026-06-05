# JobSpy RAG Tool Design

## Goal

Add JobSpy as an LLM-callable job-offer acquisition tool. The chat planner should be able to fetch fresh job offers from public job boards, persist them as Scout jobs, index them into the existing RAG corpus, and then answer using the indexed offers.

## Architecture

Use the existing provider seam in `services.job_providers` rather than adding a CLI-first path. Add a JobSpy client/adapter pair:

- `JobSpyJobProviderClient` calls `jobspy.scrape_jobs(...)` and converts the returned dataframe into raw row dictionaries.
- `JobSpyJobProviderAdapter` normalizes those rows into `JobRepository.create(...)` input.
- Existing `import_jobs(..., should_index=True)` handles persistence, duplicate URL skipping, skill enrichment, and per-job indexing.

Expose a new chat tool named `fetch_job_offers` from `chat_orchestrator._TOOLS`. The tool should be chosen when the user asks for fresh/current job offers rather than only searching the existing corpus.

## Data Flow

1. LLM receives a user request such as “find Python backend jobs in London”.
2. LLM calls `fetch_job_offers` with search term, location, sites, count, and optional filters.
3. JobSpy scrapes supported boards.
4. Scout stores created jobs in `jobs` with `source="jobspy"` and preserves the board in `raw_payload.site`.
5. Created jobs are indexed into `job_chunks` using the existing embedding provider.
6. The tool runs semantic search against the updated RAG corpus and returns matching job cards plus import stats.
7. The LLM summarizes the result without inventing jobs.

## Tool Parameters

The initial tool accepts:

- `search_term`: required job query string.
- `location`: optional location.
- `sites`: optional list of JobSpy site names; default to `indeed` for reliability.
- `count`: requested offers, bounded to a small safe limit.
- `hours_old`: optional freshness filter.
- `is_remote`: optional remote filter.
- `job_type`: optional JobSpy job type.
- `country_indeed`: optional country for Indeed/Glassdoor, default `UK`.
- `limit`: number of matching jobs to return after indexing.

## Error Handling

Validation errors return a failed tool result with a user-actionable message. Scraper/runtime failures return a failed tool result and should mention likely causes: rate limiting, unsupported site/country, database not initialized, or embedding provider misconfiguration.

Provider import runs should record JobSpy attempts with `provider="jobspy"`, including query parameters, requested count, created count, skipped duplicates, indexed count, status, and error.

## Testing And Checks

There is no repo test harness. Verification should use:

- `uv sync` after adding dependencies.
- `uv run python -m compileall main.py apps packages` for syntax/import checks.

Avoid real scraping as routine verification because it is network-dependent and may hit rate limits.

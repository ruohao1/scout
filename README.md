# Scout

Scout is a job-matching app with a FastAPI backend, React frontend, Postgres, and pgvector.

## Start

```bash
docker compose up --build
```

Open:

```txt
Web: http://127.0.0.1:5173
API docs: http://127.0.0.1:8000/docs
```

## Stop

```bash
docker compose down
```

To remove database data too:

```bash
docker compose down -v
```

## LaTeX CV Export

Compose starts a `latex-mcp` service for tailored CV exports. The API writes generated `.tex` files to a shared `latex-output` volume, calls the LaTeX MCP bridge to validate them, then compiles valid documents to PDF with `pdflatex` by default.

Useful settings:

```txt
LATEX_BRIDGE_URL=http://latex-mcp:8020
LATEX_COMPILE_ENGINE=pdflatex
```

The `latex-mcp` image installs and calls `RobertoDure/mcp-latex-server` internally. The web UI still lets you copy or download the `.tex` source, and shows a PDF download button when compilation succeeds.

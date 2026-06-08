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

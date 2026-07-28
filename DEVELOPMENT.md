# Development

## Environment

```bash
cp .env.example .env
docker compose up --build
```

## Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.commands.seed_simulators
uv run python -m app.commands.create_admin
uv run uvicorn app.main:app --reload
```

`app.commands.create_admin` reads `ADMIN_USERNAME`, `ADMIN_FULL_NAME`, and optional
`ADMIN_PASSWORD` from the environment. If `ADMIN_PASSWORD` is not set, it prints a
generated temporary password once.

Checks:

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

PostgreSQL integration tests run when `RUN_POSTGRES_TESTS=1` is set. They use
`TEST_DATABASE_URL` when it is set, otherwise
`postgresql+asyncpg://trainer:trainer@localhost:5432/trainer`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Checks:

```bash
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

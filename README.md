# Max-AI

Max-AI is a self-hosted chatbot application. It runs a Python FastAPI backend,
the existing HTML/CSS/JavaScript chat interface, PostgreSQL, and a local
GGUF-compatible model through llama.cpp. It uses existing open-weight model
artifacts; Max-AI does not train its own foundation model and does not call
OpenAI, Gemini, OpenRouter, or any other hosted AI API.

## Architecture

```text
Browser ──same-origin──> FastAPI ──private Compose network──> llama.cpp
                              │
                              └──private Compose network──> PostgreSQL
```

Only the FastAPI app is published on port 8000. PostgreSQL and llama.cpp ports
are bound to host loopback for local development and are not published to the
public network. The model weights are mounted read-only and are not included in
the application image or Git.

## Requirements

- Docker Engine and Docker Compose v2.
- A compatible GGUF model downloaded separately; see [`model/README.md`](model/README.md).
- Enough disk, RAM, and optionally VRAM for the selected model, quantization,
  context length, and other running services. A small 3B Q4 model is around
  2 GB on disk; 8 GB or more of system RAM is a practical minimum for a small
  CPU test setup, not a speed or production guarantee.
- Python 3.11+ only for running the backend and tests directly on the host.

CPU inference is the default. GPU acceleration requires a matching llama.cpp
GPU image, compatible host drivers/runtime, and explicit Compose configuration;
the project does not assume GPU availability.

## Repository structure

```text
backend/app/
  api/                 # auth, chat/conversations, health, and model routes
  core/                # cookie-session auth dependencies and rate limiting
  database/            # async SQLAlchemy engine and relational models
  schemas/              # Pydantic request/response validation
  services/             # conversation persistence and llama.cpp client
  main.py               # FastAPI app, CORS, security headers, static hosting
backend/migrations/     # Alembic environment and initial PostgreSQL migration
frontend/               # Existing single-page HTML/CSS/JavaScript UI
model/README.md         # GGUF selection, installation, licensing, hardware
model/weights/          # Local-only GGUF files; ignored by Git
tests/                  # API, auth, persistence, and mocked inference tests
Dockerfile
compose.yaml
requirements.txt
requirements-dev.txt
```

The starter already used root-level `Dockerfile` and `compose.yaml`; they remain
at those paths to preserve existing commands instead of duplicating them under
a new `deployment/` directory.

## Configure a private environment

`.env` is local configuration and is excluded from Git. The repository contains
only placeholder values in `.env.example`. If `.env` already exists, **do not
overwrite it**: edit it locally and add or replace the settings below. Old
`AI_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `OPENROUTER_API_KEY`
settings are not used by this application.

Create a database password locally:

```sh
openssl rand -hex 32
```

Put that generated value in **both** `POSTGRES_PASSWORD` and the password
portion of `DATABASE_URL` in `.env`. For example, the URL format for local
development is:

```text
postgresql+psycopg://maxai:<same-password>@localhost:5432/maxai
```

The Compose backend overrides the database hostname to `db`; do not put a real
database password in documentation, source files, or chat messages.

Useful settings:

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `development`, `test`, or `production`; production cookies require HTTPS |
| `APP_PORT` | Host port for the FastAPI app (default `8000`) |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | PostgreSQL database credentials |
| `DATABASE_URL` | SQLAlchemy URL for direct local development; Compose constructs its private `db` URL |
| `MODEL_SERVER_URL` | Private llama.cpp origin; defaults to `http://127.0.0.1:8080` for host development |
| `MODEL_NAME` | `auto` selects the first model reported by llama.cpp, or specify an exact loaded model ID |
| `MODEL_SYSTEM_PROMPT` | System instructions sent to the local model |
| `MODEL_FILE` | GGUF filename inside `model/weights/` |
| `MODEL_CONTEXT_LENGTH` | llama.cpp context size (default `4096`) |
| `MODEL_MAX_TOKENS` | Generation limit (default `512`, must be lower than context size) |
| `MODEL_GPU_LAYERS` | Layers offloaded to a supported GPU; default `0` for CPU |
| `MODEL_TIMEOUT_SECONDS` | Backend inference timeout |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Maximum login-session lifetime |
| `FRONTEND_ORIGINS` | Comma-separated explicit CORS origins; wildcard origins are rejected |
| `ALLOW_REGISTRATION` | Disable public sign-up after creating intended accounts |
| `AUTH_RATE_LIMIT`, `CHAT_RATE_LIMIT` | Per-process request limits per minute |

Authentication uses randomly generated opaque session tokens, stored only as
SHA-256 hashes in PostgreSQL and sent in HttpOnly, SameSite=Lax cookies. Since
tokens are looked up server-side rather than signed, there is no static JWT
signing secret to configure. Production cookies are marked Secure; serve the
application behind a TLS-enabled reverse proxy.

## Install a model

Review the model card and exact license before downloading or using any weights.
The suggested test model is Qwen2.5-3B-Instruct GGUF; model selection and a
manual Hugging Face CLI download command are documented in
[`model/README.md`](model/README.md). Place the selected `.gguf` file in
`model/weights/`, then set `MODEL_FILE` to its filename.

Max-AI does not download weights at application startup. The directory is
git-ignored and mounted read-only into the model container. Never commit model
weights.

## Run with Docker Compose

1. Make sure `.env` has the database and model settings described above.
2. Download a compatible GGUF file to `model/weights/`.
3. Set `MODEL_FILE` to that file and keep `MODEL_GPU_LAYERS=0` for the CPU
   default.
4. Build and start the three services:

   ```sh
   docker compose up --build -d
   ```

5. Check service status and health:

   ```sh
   docker compose ps
   curl http://localhost:8000/api/health
   curl http://localhost:8000/api/health/model
   ```

Open <http://localhost:8000>. To stop the services without deleting the
PostgreSQL volume, run `docker compose down`. Do not use `docker compose down -v`
unless you intentionally want to delete persisted application data.

If running in Codespaces, forward port 8000 to view the UI. Codespaces typically
does not provide GPU passthrough; use a model small enough for its available
CPU and memory. The model server may restart or remain unavailable if the
selected model file is missing or the machine runs out of memory.

## Host-based development

This mode runs PostgreSQL and llama.cpp in Compose while running FastAPI and the
frontend-serving app directly in the Python environment:

```sh
docker compose up -d db model-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=backend python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The Compose database and model ports are exposed to the host **only on
127.0.0.1** for this development workflow. Keep the Uvicorn terminal running
while using the site. PostgreSQL migrations are applied automatically by the
backend container in the full Compose deployment; for host-based development
run:

```sh
PYTHONPATH=backend alembic upgrade head
```

The host app loads `.env` using Pydantic Settings. Do not copy `.env.example`
over an existing private `.env`.

## Authentication and API

Create an account using the page’s registration form. Passwords must be at
least 12 characters. Registration and login are rate limited; consider setting
`ALLOW_REGISTRATION=false` after creating the accounts you intend to use.
Conversations and messages are stored in PostgreSQL and scoped to their owner.
The model endpoint and chat route require a valid session.

The existing `/api` route paths and chat response `{"reply": "..."}`
remain compatible; chat now also returns `conversation_id`. Versioned aliases
are available under `/api/v1`.

| Method | Endpoint | Access |
| --- | --- | --- |
| `GET` | `/api/health` | Public; checks backend and database |
| `GET` | `/api/health/model` | Public model-readiness status only |
| `POST` | `/api/auth/register` | Public, rate limited |
| `POST` | `/api/auth/login` | Public, rate limited |
| `POST` | `/api/auth/logout` | Clears and revokes the current session |
| `GET` | `/api/auth/me` | Authenticated |
| `POST` | `/api/chat` | Authenticated; persists user and assistant messages |
| `GET` | `/api/models` | Authenticated; lists the local model server’s loaded models |
| `GET` | `/api/conversations` | Authenticated; own conversations only |
| `GET` | `/api/conversations/{conversation_id}` | Authenticated; own conversation only |
| `DELETE` | `/api/conversations/{conversation_id}` | Authenticated; own conversation only |

Chat request example:

```json
{
  "messages": [
    { "role": "user", "content": "Hello!" }
  ]
}
```

To continue a conversation, include its `conversation_id` and the new user
message. The server loads previous messages from PostgreSQL; browser-supplied
history is not trusted for an existing conversation. Requests are limited to
40 messages with at most 4,000 characters each. Inference context is bounded
using the configured context and generation limits.

## Tests

Install development dependencies and run the test suite:

```sh
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use an isolated in-memory SQLite database and mocked llama.cpp responses.
They cover app/static/API routes, health, registration/login, password hashing,
invalid and expired/revoked sessions, protected routes, chat validation,
conversation persistence/ownership, and local inference failure handling.

**Passing mocked inference tests does not mean a real model is running.** A real
model is verified only when `/api/health/model` reports `{"status":"ok"}` and a
chat request returns a model-generated reply from the downloaded GGUF model.
Production deployment is not verified by the automated test suite.

## Troubleshooting

- **Health returns 503:** inspect `docker compose ps` and database container
  logs with `docker compose logs db backend`; verify `.env` DB values match.
- **Model health is unavailable:** confirm the selected GGUF exists at the
  configured path, inspect `docker compose logs model-server`, and check model
  compatibility, RAM/VRAM, context length, and `MODEL_GPU_LAYERS`.
- **Chat returns 503:** the backend cannot reach the local model server. Check
  that the backend uses `http://model-server:8080` in Compose or
  `http://127.0.0.1:8080` for host-based development. No external provider
  fallback is attempted.
- **Cookie is not retained in production:** serve the app over HTTPS when
  `APP_ENV=production`; production cookies are Secure.
- **Login/register throttled:** wait for the rate-limit window to expire. The
  built-in limiter is per-process; use a shared reverse-proxy limiter for
  multi-worker/public deployments.
- **Database migration errors:** check database readiness and run
  `PYTHONPATH=backend alembic upgrade head` from the project root.

## Security notes

- `.env`, `.env.*` (except `.env.example`), virtual environments, caches, and
  model weights are excluded from Git. `.dockerignore` also excludes secrets
  and weights from build context.
- Ignore rules do not erase secrets already committed in Git history. If a
  credential was committed or shared, revoke/rotate it with its issuer and
  clean repository history separately before public release.
- The app has no hosted AI-provider integration or API-key fallback. It sends
  inference only to the configured private/local llama.cpp server.
- Built-in rate limiting is process-local and intended as a basic safeguard;
  use a shared edge limiter, TLS, backups, monitoring, and an operational
  account-registration policy before exposing the service publicly.

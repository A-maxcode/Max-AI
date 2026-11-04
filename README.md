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

Only FastAPI is published for the web UI. PostgreSQL is bound to host loopback
for local development, while llama.cpp has no host-published port and is
reachable only by the backend on a private Docker network. Model weights are
mounted read-only and excluded from Git and the backend image.

## Requirements

- Docker Engine and Docker Compose v2.
- The configured 1.7B Q4_K_M GGUF model (about 1.06 GB), downloaded separately
  into `model/weights/`; see [`model/README.md`](model/README.md).
- Enough RAM for PostgreSQL, llama.cpp, its model weights and context cache.
  The Codespaces configuration targets 2 CPU cores and an 8 GiB Docker memory
  limit; inference speed depends on the Codespace allocation.
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
| `MODEL_SERVER_URL` | Internal llama.cpp URL; Compose sets `http://model-server:8080` |
| `MODEL_NAME` | `auto` selects the first model reported by llama.cpp, or specify an exact loaded model ID |
| `MODEL_SYSTEM_PROMPT` | System instructions sent to the local model |
| `MODEL_PATH` | Model path inside the model container (default `/models/smollm2-1.7b-instruct-q4_k_m.gguf`) |
| `MODEL_CONTEXT_LENGTH` | llama.cpp context size (default `2048`) |
| `MODEL_MAX_TOKENS` | Generation limit (default `256`, must be lower than context size) |
| `MODEL_THREADS` | CPU generation and prompt-processing threads (default `2`) |
| `MODEL_BATCH_SIZE` | llama.cpp prompt batch size (default `128`) |
| `MODEL_GPU_LAYERS` | Layers offloaded to a supported GPU; default `0` for CPU |
| `MODEL_TIMEOUT_SECONDS` | Backend inference timeout (default `180` seconds) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Maximum login-session lifetime |
| `FRONTEND_ORIGINS` | Comma-separated explicit CORS origins; wildcard origins are rejected |
| `ALLOW_REGISTRATION` | Disable public sign-up after creating intended accounts |
| `AUTH_RATE_LIMIT`, `CHAT_RATE_LIMIT` | Per-process request limits per minute |

Authentication uses randomly generated opaque session tokens, stored only as
SHA-256 hashes in PostgreSQL and sent in HttpOnly, SameSite=Lax cookies. Since
tokens are looked up server-side rather than signed, there is no static JWT
signing secret to configure. Production cookies are marked Secure; serve the
application behind a TLS-enabled reverse proxy.

## Assistant identity

The assistant identifies as **Max-AI**, developed by **A-maxcode**, also known
as **Angelo Besas**. The local-model system prompt reinforces this identity and
clarifies that A-maxcode developed the application, not the underlying
SmolLM2 foundation model. Direct identity questions receive canonical,
persisted answers; ordinary messages continue through llama.cpp.

## Install a model

The configured model is SmolLM2 1.7B Instruct Q4_K_M from the Hugging FaceTB
publisher repository. Its repository metadata declares Apache-2.0. The exact
source, file size, download command, CPU settings, and licensing reminder are
documented in [`model/README.md`](model/README.md).

The GGUF is downloaded to `model/weights/`; this persistent local directory is
git-ignored and mounted read-only into the model container. The application
does not download weights during startup. Never commit model weights.

## Run with Docker Compose

1. Keep your existing `.env`; do not overwrite its PostgreSQL settings. Add
   the model settings from `.env.example` if they are missing.
2. Download the GGUF using the command in [`model/README.md`](model/README.md).
   The file must exist at the path configured by `MODEL_PATH` inside the model
   container.
3. Keep `MODEL_GPU_LAYERS=0` for CPU inference.
4. Build and start the services:

   ```sh
   docker compose up --build -d
   ```

5. Check service status and both readiness endpoints:

   ```sh
   docker compose ps
   curl http://localhost:8000/api/health
   curl http://localhost:8000/api/health/model
   ```

Open <http://localhost:8000>. To stop the services without deleting the
PostgreSQL volume, run `docker compose down`. Do not use `docker compose down -v`
unless you intentionally want to delete persisted application data.

If running in Codespaces, forward port 8000 to view the UI. Codespaces typically
does not provide GPU passthrough; the configured small model runs CPU-only. The
backend waits for PostgreSQL and the model-server health checks before it
starts. If the model does not become healthy, inspect `docker compose logs
model-server` and verify the GGUF path, available memory, and CPU settings.

After startup, register through the page, send a prompt, and then send a
follow-up in the same conversation. A successful answer is generated by the
local GGUF model and both turns are persisted in PostgreSQL.

## Verify PostgreSQL and llama.cpp

Check PostgreSQL readiness and its persistent schema:

```sh
docker compose exec db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"'
```

Check llama.cpp and the backend's path to it:

```sh
docker compose ps
docker compose logs --tail=100 model-server
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://model-server:8080/health', timeout=5).status)"
curl http://localhost:8000/api/health/model
```

The model service is not published to the host; reach it through Docker's
`model-server` hostname from the backend container. Migrations run
automatically before the backend starts.

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
- **Model health is unavailable:** confirm `MODEL_PATH` points to the mounted
  GGUF, inspect `docker compose logs model-server`, and check model
  compatibility, available RAM, context length, and CPU settings.
- **Chat returns 503:** the backend cannot reach the local model server. Check
  that Compose sets `MODEL_SERVER_URL=http://model-server:8080` and that the
  model service is healthy. No external provider fallback is attempted.
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

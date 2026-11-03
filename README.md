# My AI Assistant

A server-ready AI assistant starter with a Python FastAPI backend and a plain
HTML, CSS, and JavaScript frontend. The backend calls an OpenAI-compatible chat
completions API; provider credentials stay on the server.

## Project structure

```text
backend/
  app/
    main.py              # HTTP endpoints and frontend hosting
    config.py            # Server-side environment configuration
    schemas.py           # Validated chat request and response models
    services/chat.py     # OpenAI-compatible provider integration
frontend/
  index.html             # Chat page
  styles.css             # Responsive styling
  app.js                 # Browser chat behavior
Dockerfile
compose.yaml
requirements.txt
```

## Run locally

Requires Python 3.11 or newer.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `AI_API_KEY` in `.env` to a key from your chosen provider, then run:

```sh
PYTHONPATH=backend uvicorn app.main:app --app-dir backend --reload
```

Open <http://localhost:8000>. The health endpoint is at
<http://localhost:8000/api/health>, and the interactive API docs are at
<http://localhost:8000/docs>.

## Deploy with Docker Compose

Copy `.env.example` to `.env`, set `AI_API_KEY` and any provider-specific
settings, then start the server:

```sh
docker compose up --build -d
```

The app listens on port `8000`. Put it behind a TLS-enabled reverse proxy for
public deployments, and keep `.env` private and out of version control.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `My AI Assistant` | API title |
| `AI_API_KEY` | unset | Server-side provider API key |
| `AI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL |
| `AI_MODEL` | `gpt-4o-mini` | Provider model name |
| `AI_SYSTEM_PROMPT` | Friendly assistant prompt | Instructions sent to the model |
| `AI_TIMEOUT_SECONDS` | `60` | Provider request timeout |

The chat endpoint accepts `POST /api/chat` with a `messages` array containing
`user` and `assistant` messages. Each message is limited to 4,000 characters
and each request to 40 messages. Conversation history currently lives in the
browser and is sent with each request; it is not stored on the server.

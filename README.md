# LuminaLib — Intelligent Library System (Technical Challenge)

## Quick start (one-command)
Run:

```bash
docker compose up -d --build
```

This starts:
- API: http://localhost:8000
- Mock LLM: http://localhost:5100
- Postgres, Redis, MinIO, and Celery worker

## Auth & Admin Access
- Only the user whose  username is `rootuser` can upload, update, or delete books.
- Create this admin user first, then log in and use the returned access token.
 - Profile endpoints: `GET /auth/me`, `PUT /auth/me` (requires `current_password`).
 - Signout endpoint: `POST /auth/signout` (revokes token until expiry).

## LLM Provider: Mock vs Ollama
By default the system uses the lightweight mock LLM container included in `docker-compose.yml`.

### Mock LLM (default)
- Set `LLM_PROVIDER=mock`
- Set `MOCK_LLM_URL=http://mock_llm:5100`
- This is fast, deterministic, and good for demos/tests.

### Ollama (local LLM)
- Set `LLM_PROVIDER=ollama`
- Set `OLLAMA_URL=http://ollama:11434`
- Set `OLLAMA_MODEL=llama3` (or any model installed in Ollama)

Note: If you choose Ollama, you must run an Ollama container/service reachable at `OLLAMA_URL`. The code expects the standard `/api/generate` endpoint.

Steps:
1. Create user with username  `rootuser`.
2. Log in to get `access_token`.
3. Use the token in Swagger:
   - Open `http://localhost:8000/docs`
   - Click **Authorize**
   - Enter `Bearer <access_token>`
4. You can now upload/update/delete books. Other users can only view/borrow/review/get recommandations /review analysis.

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

Steps:
1. Create user with username  `rootuser`.
2. Log in to get `access_token`.
3. Use the token in Swagger:
   - Open `http://localhost:8000/docs`
   - Click **Authorize**
   - Enter `Bearer <access_token>`
4. You can now upload/update/delete books. Other users can only view/borrow/review/get recommandations /review analysis.

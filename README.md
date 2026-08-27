# Company Document Chatbot MVP

Production-oriented FastAPI chatbot using PostgreSQL/pgvector retrieval with switchable offline mock and OpenAI providers. Mock mode is the default and makes no external AI calls. Documents and application history stay in PostgreSQL. In OpenAI mode, only the user question, up to `MAX_CONTEXT_CHUNKS` relevant excerpts, and six recent short messages are sent to OpenAI; response storage is disabled.

## Local setup (Windows PowerShell)

Prerequisites: Python 3.12 and Docker Desktop.

```powershell
Copy-Item .env.example .env
# Keep AI_PROVIDER_MODE=mock and OPENAI_API_KEY empty; set a random ADMIN_API_KEY (24+ characters)
$env:POSTGRES_PASSWORD = "choose-a-local-password"
# Use the same password in DATABASE_URL if running Python outside Docker.
docker compose up -d db
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic upgrade head
pytest
uvicorn app.main:app --reload
```

Open http://localhost:8000. API documentation is at http://localhost:8000/api/docs.

## Browser voice support

The chat UI supports optional, browser-only voice input and playback at no API cost. Click the microphone to start speech recognition, choose English (India) or Hindi (India), review the recognized text in the input, and send it normally. Use the speaker beside an assistant response to read it aloud; voice, language, speed, and stop controls are above the composer.

- Voice input requires the Web Speech Recognition API (`SpeechRecognition` or `webkitSpeechRecognition`). Chromium-based browsers generally provide the best support; availability varies by browser and operating system.
- Response playback requires the Web Speech/SpeechSynthesis API. Available voices come from the browser or operating system, so an exact `en-IN` or `hi-IN` voice may not always be installed.
- Microphone access requires a secure context (`https://`) or `http://localhost` and is requested only after clicking the microphone button.
- Audio is never uploaded to this application backend. Web Speech Recognition is browser-managed and, depending on the browser, the browser vendor may process speech remotely under its own terms.
- If an API is unsupported or microphone permission is denied, the UI shows a notice and text chat remains fully usable.

To run everything in containers, set `DATABASE_URL` in `.env` to the `db` hostname shown in `.env.example`, then:

```powershell
docker compose up --build
```

## API examples

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/ready
curl.exe -X POST http://localhost:8000/api/admin/documents -H "X-Admin-API-Key: YOUR_ADMIN_KEY" -F "file=@.\company-faq.txt;type=text/plain"
curl.exe http://localhost:8000/api/admin/documents -H "X-Admin-API-Key: YOUR_ADMIN_KEY"
curl.exe -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"message":"What services do you provide?"}'
curl.exe -X POST http://localhost:8000/api/leads -H "Content-Type: application/json" -d '{"name":"Alex","company":"Example Ltd","email":"alex@example.com","phone":"+91 9876543210","requirement":"Please contact me about implementation."}'
```

## Configuration

`AI_PROVIDER_MODE` accepts `mock` (default) or `openai`. Mock mode uses deterministic local embeddings and returns a clearly labelled sample answer composed from retrieved document excerpts; it needs no AI key and makes no external AI calls. To enable OpenAI later, set `AI_PROVIDER_MODE=openai` and provide `OPENAI_API_KEY`. Selecting OpenAI without a key returns a safe service configuration error without stopping the application.

Required: `DATABASE_URL` and `ADMIN_API_KEY` (24+ characters); `OPENAI_API_KEY` is required only in OpenAI mode. Configurable: `OPENAI_MODEL` (default `gpt-5.6-luna`), `EMBEDDING_MODEL` (default `text-embedding-3-small`), `ALLOWED_ORIGINS` (comma-separated), `MAX_UPLOAD_MB`, `MAX_CONTEXT_CHUNKS`, `MONTHLY_TOKEN_LIMIT`, `RATE_LIMIT_PER_MINUTE`, `EMBEDDING_DIMENSIONS`, and `MAX_ANSWER_TOKENS`.

Changing `EMBEDDING_DIMENSIONS` requires an accompanying migration; the initial schema uses 1536 dimensions.

## AWS deployment checklist

- Push the image to ECR and deploy it on ECS Fargate or App Runner behind an HTTPS load balancer.
- Use Amazon RDS for PostgreSQL with pgvector enabled; run `alembic upgrade head` as a one-off deployment task.
- Store secrets in AWS Secrets Manager or SSM Parameter Store and inject them into the task definition.
- Restrict RDS to private subnets/security groups; give the application least-privilege IAM permissions.
- Add WAF/API Gateway or load-balancer rate limits for distributed production traffic. The included in-process limiter is only a basic MVP guard and is per container.
- Send application logs (which omit document bodies and lead values) to CloudWatch; add alarms, backups, Multi-AZ as required, and an RDS Proxy if connection pressure warrants it.
- Set exact production `ALLOWED_ORIGINS`, rotate the admin key, configure health checks (`/health`) and readiness checks (`/ready`), and run load/security tests before launch.

The MVP stores original documents in PostgreSQL. For larger scale, an approved follow-up can move originals to encrypted S3 while retaining metadata and vectors in PostgreSQL.

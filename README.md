# Real Estate Voice Agent

A browser MVP for testing real-estate enquiry conversations, deterministic property
search, lead capture, and idempotent viewing bookings. It includes a provider-free
text flow and optional realtime voice powered by Qwen.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn apps.api.main:app --reload
```

Open `http://localhost:8000/docs` for the API. In another terminal, start the console:

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`. The database is created and populated with 32 synthetic
listings on first API startup. Use `http://localhost:3000/review` to inspect recorded
calls, transcripts, preferences, matches, tool activity, latency, and bookings. No
provider key is required for the text flow.

## Qwen realtime voice

The text flow remains available without a provider. To enable the optional voice flow,
set these values in the ignored root `.env` file:

```dotenv
DASHSCOPE_API_KEY=your-key
QWEN_REALTIME_MODEL=qwen3.5-omni-flash-realtime
```

Verify the server-side connection without exposing the key:

```powershell
python -m scripts.check_qwen_realtime
```

Then run the API and web console, open `http://localhost:3000`, and select **Start
voice**. Allow microphone access and use headphones to avoid echo-triggered
interruptions. Audio travels through the FastAPI WebSocket proxy; the browser never
receives the provider credential. Live caller and assistant transcripts appear during
speech; speaking over the assistant cancels queued playback.

## Booking confirmation email

For Render Free, use Brevo's HTTPS transactional-email API. Register and verify the
sender address in Brevo, create an API key, and configure:

```dotenv
EMAIL_DELIVERY_MODE=brevo
BREVO_API_KEY=your-brevo-api-key
BREVO_API_URL=https://api.brevo.com/v3/smtp/email
BOOKING_FROM_EMAIL=your-verified-sender@example.com
BOOKING_FROM_NAME=Horizon Homes
```

Gmail SMTP remains available for local development or hosts that allow SMTP. Add your
full Gmail address and a Google App Password to the ignored root `.env` file:

```dotenv
EMAIL_DELIVERY_MODE=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-gmail-address@gmail.com
SMTP_PASSWORD=your-16-character-google-app-password
SMTP_START_TLS=true
SMTP_USE_SSL=false
BOOKING_FROM_EMAIL=your-gmail-address@gmail.com
```

Use an App Password rather than your normal Google password. The Google account must
have 2-Step Verification enabled. The booker's email is required for a viewing and is
used only for the confirmation. Idempotent retries do not resend a delivered message.

## Deploy to Render

The root `render.yaml` defines a free FastAPI web service and a free static Next.js
site. Use an external PostgreSQL database such as Neon because local SQLite files do
not persist on Render Free.

1. Push the repository to GitHub and create a Neon database.
2. In Render, select **New > Blueprint** and connect the repository.
3. Enter the requested secret values. For `DATABASE_URL`, change Neon's
   `postgresql://` prefix to `postgresql+psycopg://`.
4. For the first deployment, use temporary valid URLs for `WEB_ORIGIN` and
   `NEXT_PUBLIC_API_URL`, such as `https://example.invalid`.
5. After Render creates both services, set `NEXT_PUBLIC_API_URL` on the static site to
   the API's `https://...onrender.com` URL and trigger a new static-site deploy.
6. Set `WEB_ORIGIN` on the API to the static site's `https://...onrender.com` URL and
   redeploy the API.
7. Verify `/health`, then test voice, booking, email delivery, and the review page.

Keep all keys in Render's environment settings. Never commit `.env` or paste secrets
into `render.yaml`.

To run the complete containerized stack:

```powershell
docker compose up --build
```

## Validation

```powershell
pytest
ruff check .
cd apps/web
npm run lint
npm run typecheck
npm test
```

All data is synthetic. The fuller roadmap and production safeguards are documented in
`real_estate_voice_agent_implementation_plan.md`.

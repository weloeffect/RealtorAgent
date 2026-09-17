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

The project is configured for Gmail SMTP. Add your full Gmail address and a Google App
Password to the ignored root `.env` file:

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

# Real Estate Voice Agent

A local, provider-free MVP for testing real-estate enquiry conversations, deterministic
property search, lead capture, and idempotent viewing bookings.

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

Open `http://localhost:3000`. The database is created and populated with synthetic
listings on first API startup. No provider keys are required.

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

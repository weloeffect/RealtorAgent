# Repository Guidelines

## Project Structure & Module Organization

The implementation follows `real_estate_voice_agent_implementation_plan.md`. Keep additions within the established layout:

- `apps/api/` contains the FastAPI service and tests; reserve `apps/voice_gateway/` and `apps/worker/` for later Python services.
- `apps/web/` contains the Next.js/TypeScript voice/text console and call-review UI.
- `packages/domain/`, `packages/tools/`, and `packages/providers/` for reusable business rules, model tools, and external-service adapters.
- `packages/prompts/` and `packages/evals/` for versioned prompts, scenarios, rubrics, and reports.
- `infra/docker/` and `infra/deploy/` for local and deployment configuration; `docs/architecture/` for decisions, diagrams, and runbooks.

Keep tests beside the relevant service in `tests/`, and store only synthetic, non-sensitive fixtures.

## Build, Test, and Development Commands

Use these entry points and document any future deviation in the root README:

- `docker compose up --build` — start the API, web app, PostgreSQL, and Redis.
- `pytest` — run Python unit and integration tests.
- `npm test` — run web unit tests from `apps/web/`.
- `npx playwright test` — run browser voice and console flows.
- `npm run lint` and `npm run typecheck` — validate TypeScript.

## Coding Style & Naming Conventions

Use four spaces in Python and two spaces in TypeScript, JSON, and YAML. Add Ruff plus a Python type checker, and ESLint/Prettier for web code. Use `snake_case` for Python modules/functions, `PascalCase` for Python and React classes/components, and `camelCase` for TypeScript values. Name adapters by provider and capability, such as `twilio_voice.py`; keep provider-specific logic out of the domain package.

## Testing Guidelines

Use Pytest (plus Hypothesis for invariants), Playwright for end-to-end tests, and k6 for load tests. Name Python tests `test_<behavior>.py` and evaluation scenarios with stable descriptive IDs. Cover state transitions, schema rejection, consent, redaction, idempotency, webhook replay, tenant isolation, booking concurrency, and provider failures. Every bug fix should include a regression test.

## Commit & Pull Request Guidelines

Git history is unavailable, so use Conventional Commits such as `feat(api): add property search` or `fix(booking): reject duplicate slot claims`. Keep commits focused. Pull requests should explain behavior and risks, link the relevant issue or plan section, list validation commands, and include screenshots for UI changes. Call out schema, prompt, provider, privacy, or deployment changes explicitly; never commit secrets or real customer data.

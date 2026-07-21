# AGENTS.md

These rules apply to the entire repository.

## Architecture

- Preserve the monorepo boundary: Django code belongs in `backend/`, while Nuxt and Vue code belongs in `frontend/`.
- Do not mix backend concerns into frontend components or frontend concerns into Django modules. Communicate through documented HTTP APIs.
- Keep public REST endpoints under `/api/v1/`. Schema and documentation endpoints may remain under `/api/`.
- Prefer the smallest clear implementation. Do not introduce infrastructure or abstraction before it is needed.

## Dependencies and code quality

- Add a dependency only when the standard library or existing dependencies cannot reasonably solve the problem, and document the reason in the task handoff.
- Write tests for business logic and regressions. Keep tests close to the relevant application area.
- Use TypeScript without `any`. If an exceptional integration requires `any`, explain it next to the narrowest possible usage.
- Do not silence linters or type errors without a specific, documented reason.
- Keep components and modules focused; extract reusable behavior rather than growing oversized files.

## Security and workflow

- Never commit credentials, tokens, production secrets, or populated local `.env` files. Update `.env.example` with safe placeholders when configuration changes.
- Run the relevant tests, linters, type checks, and builds before completing a task. State exactly which checks were and were not run.
- Do not make Git commits or push changes unless the user explicitly requests it.
- Avoid unrelated edits and preserve user changes already present in the working tree.

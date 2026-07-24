# AGENTS.md

These rules apply to the entire repository.

## Architecture

- Preserve the monorepo boundary: Django code belongs in `backend/`, while Nuxt and Vue code belongs in `frontend/`.
- Do not mix backend concerns into frontend components or frontend concerns into Django modules. Communicate through documented HTTP APIs.
- Keep public REST endpoints under `/api/v1/`. Schema and documentation endpoints may remain under `/api/`.
- Treat `Invitation.publication_status` as a security boundary: recipient-facing reads and mutations must expose only `published` invitations, while drafts require the matching management capability.
- Keep the builder restricted to `extended` invitations in `draft` state. Store navigation state in the route query and never place the management token in query parameters or path segments.
- Keep builder autosave sequential and idempotent: debounce ordinary edits, flush before navigation, send only the minimal PATCH, and preserve edits made while a request is in flight.
- Keep extended invitation screens complete and unique: exactly one configuration per supported screen type, stable API ordering, and no screen rows for newly created quick invitations.
- Keep the built-in image catalog local, deterministic, accessible, and keyed by stable values that remain compatible with the owning screen type. Do not add third-party image URLs to invitation screen configuration.
- Preserve idempotent lifecycle transitions and their original timestamps when requests are retried.
- Prefer the smallest clear implementation. Do not introduce infrastructure or abstraction before it is needed.

## Dependencies and code quality

- Base framework and library decisions on their current official documentation. Use third-party articles only as supplementary context.
- Add a dependency only when the standard library or existing dependencies cannot reasonably solve the problem, and document the reason in the task handoff.
- Write tests for business logic and regressions. Keep tests close to the relevant application area.
- New business logic must not reduce the established coverage gates. Every bug fix must include a regression test that fails before the fix.
- Expand the measured coverage scope as test infrastructure grows; never exclude application code only to make a percentage pass.
- Use TypeScript without `any`. If an exceptional integration requires `any`, explain it next to the narrowest possible usage.
- Do not silence linters or type errors without a specific, documented reason.
- Keep components and modules focused; extract reusable behavior rather than growing oversized files.

## Security and workflow

- Never commit credentials, tokens, production secrets, or populated local `.env` files. Update `.env.example` with safe placeholders when configuration changes.
- Run `make quality` before completing a task when the environment supports Docker. Otherwise run every available subset and state exactly which checks were and were not run.
- Do not make Git commits or push changes unless the user explicitly requests it.
- Avoid unrelated edits and preserve user changes already present in the working tree.

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
- Treat screen configuration as a separate autosaved resource: validate image compatibility on both sides, reject unknown fields, keep exact PATCH retries idempotent, and expose only recipient-safe screen fields publicly.
- Keep the invitation and acceptance screen editors independent: each owns its autosave state and image selection, while navigation must flush both resources before leaving the first builder step.
- Keep builder preview state client-only and independent from autosave: it may use demonstration dates and activities, but must never send them to the API or read the management token. Sync its default screen to the builder step while preserving direct user interaction within that step.
- Treat `Invitation.planning_mode` as a lifecycle contract: quick invitations always plan after acceptance, preconfigured options are editable in an extended draft, pending or declined recipients cannot read those options, and publication freezes the chosen mode and ordinary option editing.
- Reuse one date-option editor across the builder and management page. Preserve submitted array order as `position`, keep two–five future options as the shared validation contract, and flush valid dirty drafts before navigation.
- Keep builder date preview data client-only: it may reflect unsaved local option drafts immediately, but demonstration values and preview selections must never be persisted through the planning API.
- Drive the recipient date-selection screen from the latest public server snapshot: use the `date_selection` configuration, expose only future options relative to `server_now`, preserve author order, and allow the saved choice to change only until final confirmation.
- Reopen a published option set only when its selected option is both expired and unconfirmed. Recovery must atomically replace the whole set, clear the stale selection, preserve the invitation mode and publication state, reject future or confirmed selections, and keep exact retries idempotent.
- Keep activity options owned by one extended invitation and ordered by their submitted array position. The first management API replaces the complete collection atomically, accepts three–six draft options, keeps exact retries idempotent, and freezes edits after publication.
- Keep recipient activity selection public only for accepted published extended invitations. Expose prepared activities only after acceptance, allow one mutable selection until final confirmation, preserve exact retries, reject foreign options, and require an activity before confirming when the invitation has activity choices.
- Bind final confirmation to the exact date/activity combination shown to the author. Submit both expected UUIDs, lock the invitation while comparing them with the latest selections, reject stale activity snapshots, and render the same combined plan details before and after confirmation on both capabilities.
- Store the IANA time-zone name with every planning option and format shared final data in that saved zone rather than whichever browser happens to render the page.
- Treat `ConfirmedPlan` as an immutable display snapshot created exactly once inside the confirmation transaction. Public and management final cards must read that snapshot, not mutable invitation names, screen rows, or option rows; exact confirmation retries must return the original snapshot without changing timestamps.
- Drive the public recipient page as one explicit stage derived from the latest server snapshot: invitation, date selection, activity selection, waiting for the author, or final plan. Render only one main stage at a time; the acceptance screen may be a short local transition after a successful response, but a reload must resume from persisted server state.
- Keep the real recipient decline action direct and pressure-free. The playful runaway-button behavior may remain in builder preview only; a persisted decline must render a separate neutral stage, allow one explicit change to acceptance only before final confirmation, and never expose a decline control after a confirmed plan exists.
- Restore the recipient flow only from the latest public server snapshot. On initial reopen, explain recovered progress without blocking the active stage; when a selected date expires, clear its local usable state and return to date selection; when a background tab becomes visible again, refresh with a cooldown without overwriting an unsaved local choice, and keep refresh failures non-destructive.
- Keep public invitation social metadata server-rendered and recipient-safe. Use only generic Date Planner copy and a local static preview image; never place author names, recipient names, messages, selected options, final-plan details, management paths, tokens, query parameters, or URL fragments into Open Graph, Twitter, canonical, or document-title metadata.
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

## Production configuration

- Keep local HTTP defaults usable, but make every production transport decision explicit through environment variables.
- Never enable forwarded HTTPS trust unless the deployment proxy overwrites `X-Forwarded-Proto`; keep DRF's proxy count consistent with the real trusted chain.
- Keep the synthetic deployment check warning-free in CI. Run the same check with real deployment values and review any platform-specific warnings before release.
- Treat `.env.production.example` as documentation only. Real secrets and passwords belong in the deployment platform, never in Git or task archives.
- Introduce HSTS gradually: verify HTTPS first, then increase duration and opt into subdomains or preload only when the whole domain is ready.

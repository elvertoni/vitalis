# Repository Guidelines

## Project Structure & Module Organization

Vitalis is a Django 6 application. `config/` contains project settings and root URLs; `core/` provides shared models, validators, owner-scoped CRUD views, and mixins. Domain apps are `accounts/`, `saude/`, `treino/`, `nutricao/`, `lembretes/`, and `billing/`. Each app keeps models, forms, views, URLs, admin registration, and migrations together. Shared UI lives in `templates/`; app-specific templates use `templates/<app>/`. Treat `design_system/design-system.html` as the visual source of truth. Consult `PRD-vitalis.md`, `PROMPT-EXEC-vitalis.xml`, and `DECISIONS.md` before changing scope or established architecture.

## Build, Test, and Development Commands

Use the checked-in Windows virtual-environment convention:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

Run `.\.venv\Scripts\python manage.py check` for Django configuration validation. After model changes, run `manage.py makemigrations` and inspect the generated migration before applying it. Use `manage.py send_due_reminders` to exercise reminder synchronization and console email delivery. Use `manage.py seed_medico --email <email> --source <dossier.json> [--attachments-dir <dir>]` to load a personal health dossier; the command carries no data of its own and is idempotent. The example payload is `medico-seed.example.json`; real dossiers live in `medico-data/` and `medico-seed.json`, both gitignored as sensitive health data (DECISIONS.md D-041).

## Coding Style & Naming Conventions

Follow PEP 8 with four-space indentation, single quotes, and descriptive English identifiers (`WorkoutSession`, `quantity_g`). Keep all interface text, form labels, and `verbose_name` values in pt-BR. Use Django conventions: `PascalCase` classes, `snake_case` functions and fields, and one class-based view per CRUD operation. Reuse `OwnedModel`, `Owner*View`, `ChildCreateView`, and `StyledFormMixin`; do not duplicate ownership filtering or input styling. Reuse the shared partials (`partials/_field.html`, `_empty_state.html`, `_pagination.html`, `_logo.html`) instead of hand-written markup. Never use `on_delete=PROTECT` between two models owned by the same user (DECISIONS.md D-021); a shared catalogue such as `billing.Plan` is the only legitimate case. No formatter or linter is currently configured.

## Testing Guidelines

The repository intentionally has no automated test suite. Validate changes with `manage.py check`, migrations, and focused browser smoke tests. Exercise create/read/update/delete flows, authentication, validation errors, and cross-user access; another user's object must return 404 and relational form choices must remain owner-scoped.

Production on the VPS is the source of truth for user accounts, subscriptions, deployed configuration, and published behavior. For any validation involving those areas, verify production first through the authenticated EasyPanel MCP connector (`work` project, `vitalis` service); use `db.sqlite3` and the local server only for complementary development checks. Do not try SSH first. If the EasyPanel connector is unavailable, state that limitation explicitly and never infer production state from local data.

The `vitalis-backup` service runs daily via `scripts/backup.sh`, creating verified (`gzip -t`) dumps of PostgreSQL and `/app/media` attachments. Backups are retained locally for 30 days and synchronized externally to the owner's Google Drive (`backup-vitalis` folder) using rclone with OAuth 2.0 Desktop credentials (DECISIONS.md D-055, D-056).

## Training: logging screen vs. CRUD

`/treino/registrar/` is the weekly path (D-048): pick the routine day, log the whole workout
in one POST. The session CRUD stays as "Sessão avulsa" for corrections and off-routine
workouts. Three rules when touching it: the GET never writes — form fields are keyed by the
target (`t<target_pk>s<n>reps`), and the session plus its entries are created in the POST only
when numbers arrived, so an abandoned visit leaves no phantom session (D-049);
`RoutineExerciseTarget.rest_seconds` is the prescription that arms the timer while
`SessionEntry.rest_seconds` is what was actually rested, and any new prescription field must
also reach `RoutineExerciseTargetForm`; `WorkoutSession.morning_after` is a queried column,
not a note, because `progression.morning_streak` counts weeks without a `worse` answer
(D-050). `treino/progression.py` is pure calculation: it suggests a load increase only when
every prescribed set hit the top of the rep range (+5 kg for leg groups, +2.5 kg otherwise),
and time-based prescriptions (`45s`) never progress by reps. The suggestion is displayed,
never written automatically.

## Commit & Pull Request Guidelines

History uses Conventional Commit prefixes, mainly `feat:` and `chore:`, followed by concise Portuguese summaries (for example, `feat: Vitalis S5 — lembretes + dashboard consolidado`). Keep each commit focused and include migrations with their model changes. Pull requests should explain behavior and architectural impact, list manual checks, link the relevant requirement or issue, and include before/after screenshots for UI changes.

## Security & Configuration

Never commit `.env`, `db.sqlite3`, uploaded `media/`, collected `staticfiles/`, real health dossiers (`medico-data/`, `medico-seed.json`), or secrets. Configuration follows fail-closed principles: `DJANGO_DEBUG` defaults to `0`, requiring explicit `DJANGO_SECRET_KEY` in production (raising `RuntimeError` if missing). If `EMAIL_HOST` is unset in production, `dummy.EmailBackend` is used to prevent leaking password reset tokens and clinical data to server logs. Rate limiting is enforced on auth views (`/contas/entrar/`, `/contas/recuperar-senha/`, `/contas/cadastrar/`) via `core.ratelimit`. Attachments validate binary magic bytes before storage. Global WhatsApp management requires `is_superuser` or `lembretes.manage_whatsapp`. Webhooks validate `x-signature` HMAC and enforce idempotency via `ProcessedWebhookEvent`. Subscriptions track active duration via `expires_at` and fallback gracefully to `Free` when expired. CSP is enforced globally via `core.middleware.SecurityHeadersMiddleware`. Serve sensitive attachments only through authenticated, owner-checking views.

## Known Gaps

The S1–S6 roadmap is delivered, but these are deliberate or pending gaps, not bugs to fix in passing: full account deletion and data export (LGPD) are not implemented; the Mercado Pago gateway has never run against a real seller account; there is no reference food catalogue (TACO), no automatic workout reminder, and no delivery channel other than email. See the "O que ainda não existe" section of `CLAUDE.md`.

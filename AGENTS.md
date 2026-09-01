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

Run `.\.venv\Scripts\python manage.py check` for Django configuration validation. After model changes, run `manage.py makemigrations` and inspect the generated migration before applying it. Use `manage.py send_due_reminders` to exercise reminder synchronization and console email delivery.

## Coding Style & Naming Conventions

Follow PEP 8 with four-space indentation, single quotes, and descriptive English identifiers (`WorkoutSession`, `quantity_g`). Keep all interface text, form labels, and `verbose_name` values in pt-BR. Use Django conventions: `PascalCase` classes, `snake_case` functions and fields, and one class-based view per CRUD operation. Reuse `OwnedModel`, `Owner*View`, `ChildCreateView`, and `StyledFormMixin`; do not duplicate ownership filtering or input styling. No formatter or linter is currently configured.

## Testing Guidelines

The repository intentionally has no automated test suite. Validate changes with `manage.py check`, migrations, and focused browser smoke tests. Exercise create/read/update/delete flows, authentication, validation errors, and cross-user access; another user's object must return 404 and relational form choices must remain owner-scoped.

## Commit & Pull Request Guidelines

History uses Conventional Commit prefixes, mainly `feat:` and `chore:`, followed by concise Portuguese summaries (for example, `feat: Vitalis S5 — lembretes + dashboard consolidado`). Keep each commit focused and include migrations with their model changes. Pull requests should explain behavior and architectural impact, list manual checks, link the relevant requirement or issue, and include before/after screenshots for UI changes.

## Security & Configuration

Never commit `.env`, `db.sqlite3`, uploaded `media/`, or secrets. Configuration comes directly from environment variables such as `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and `MERCADOPAGO_ACCESS_TOKEN`. Serve sensitive attachments only through authenticated, owner-checking views.

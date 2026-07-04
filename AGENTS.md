# AGENTS.md — Gourmet

## Dev environment

- Everything runs in Docker. Do not run python/npm directly on the host.
- `make init` — builds images, runs migrations, sets up pre-commit.
- `make run` — `docker compose up` (app, db, tailwind).
- `make test` — `docker compose run --rm app pytest`.
- Single file test: `docker compose run --rm app pytest gourmet/apps/accounts/tests.py -k test_name`.
- `docker compose run --rm app bash` to enter a container.
- `npm run seed` — `docker compose run --rm app python manage.py seed_today`.
- `npm run test:e2e` — seeds today's data then runs Playwright E2E tests.
- E2E tests in `tests/e2e/` use Playwright against `localhost:8000` (app must be running).

## Verification pipeline

`ruff check . && mypy . && pytest` — run all three before considering changes done.

## Config

- Uses `goodconf` — reads `gourmet.yml` at startup, env vars override.
- All available env vars documented in `gourmet/config.py`.
- `DJANGO_ENV` default is `production` — set to `development` in compose.yaml.
- `DJANGO_ENV=production` activates HTTPS redirect, HSTS, secure cookies, Redis cache.

## Architecture

- Central Ninja API at `gourmet/apps/accounts/api.py` — mounts routers for menu, tables, jukebox.
- `TokenAuth`: reads `Authorization: Bearer <token>`, looks up `AuthToken` model.
- `AdminTokenAuth`: same but requires `is_staff=True`.
- All write endpoints require auth; public endpoints use `auth=None`.
- Service layer at `gourmet/apps/*/services.py` — API views delegate here.
- Paginated endpoints use `@paginate` — response shape is `{"count": int, "items": [...]}`.

## App structure

- `gourmet/apps/accounts/` — auth, roles, users.
- `gourmet/apps/menu/` — categories, products. Product includes `tax_type` field (INC_8, IVA_19, IVA_5, EXENTO).
- `gourmet/apps/tables/` — restaurant tables.
- `gourmet/apps/orders/` — orders, items, payments. OrderItem snapshots `tax_rate` from product. `checkout()` computes `total = subtotal + tax`.
- `gourmet/apps/inventory/` — stock, recipes, movements. `_deduct_inventory` runs during `add_item`.
- `gourmet/apps/jukebox/` — queue + remote player integration.
- Shared: `gourmet/apps/exceptions.py` (exception handlers), `gourmet/apps/schemas.py` (MessageOut), `gourmet/apps/middleware.py` (RequestID).

## Colombian tax rules

- Restaurants with table service → **INC 8%** (Impuesto al Consumo). Franchises → **IVA 19%**.
- Fast food / autoservice / takeout without table service → **IVA 19%**. Catering → **IVA 19%**.
- Small restaurants (ingresos < 3.500 UVT ~ $183M COP/year, 1 local) → no INC, no IVA.
- UVT 2026: $52,374 COP.
- DEE POS (Documento Equivalente Electrónico) replaces paper tickets — XML + CUFE/QR, transmitted to DIAN in real time (not yet implemented in code).

## Testing quirks

- **App tests** use `tests.py` filenames discovered via `python_files = ["test_*.py", "*_test.py", "tests.py"]` in pyproject.toml.
- **Server tests** (`tests/server/`) spawn a real gunicorn subprocess per module — expensive. First test in each module needs `timeout=3` because Django initialization on first request is slow.
- `GUNICORN_CMD_ARGS` from Dockerfile ENV leaks into subprocess env in server tests — must override to empty string in test fixture (already done in `tests/server/conftest.py`).
- `--reuse-db` is default; use `--create-db` to force recreation.
- `--disable-socket` is default; `--allow-hosts=127.0.0.1,localhost` permits server test connections.
- `pytest-env` sets `DEBUG=0`, `SENTRY_DSN=""`, `TEMPLATE_DEBUG=1` for all tests.

## Gotchas

- `python manage.py ensure_superuser` does NOT accept `--noinput` — entrypoint calls it without flags.
- `uv sync --locked` in Dockerfile requires `uv.lock` to be in sync with `pyproject.toml` — run `uv lock` on host after dep changes.
- `makemigrations` must be run inside the container when models change.
- Pre-commit runs: ruff-check (with --fix), ruff-format, mypy (inside Docker), yamllint, cog (generates README sections), prettier (inside Docker with profile), hadolint.

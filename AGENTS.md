# Repository Guidelines

## Project Structure & Module Organization
- Core backend lives in `web_server.py` (Flask + Socket.IO entrypoint).
- Data and integration logic is in `database.py`, `integrations.py`, `courier_integration.py`, and `pos_integration.py`.
- Frontend assets are under `web/` (`index.html`, page-specific `.html`, shared `script.js` and `styles.css`).
- Runtime/config data files live at repo root: `menu.txt`, `waiters.json`, `salons.json`, `integrations.json`, `active_adisyonlar.json`, and generated `config.txt`.
- Utility/test scripts include `test_shifts.py`, `test_pos.py`, and `scripts/whatsapp_simulator.py`.

## Build, Test, and Development Commands
- `python3 web_server.py`: run the app locally.
- `make run`: run via project virtualenv (`.venv`) configuration.
- `make install`: install dependencies from `requirements.txt`.
- `python3 test_shifts.py`: API flow smoke test for kasa/vardiya lifecycle.
- `python3 test_pos.py`: local TCP POS simulator for payment integration checks.
- `make deploy` / `make status` / `make logs`: remote service sync and diagnostics (configured for `vet@kuvoz.local`).

## Coding Style & Naming Conventions
- Python: follow PEP 8, 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes.
- Keep existing domain terminology consistent (`masa`, `paket`, `vardiya`, `adisyon`) across API, DB, and UI labels.
- Prefer small, focused functions; avoid mixing transport (HTTP/socket) and business logic in the same block when adding new code.
- Frontend: keep shared behavior in `web/script.js`; avoid duplicating inline scripts across pages.

## Testing Guidelines
- Current tests are script-based integration checks (not a full unit test suite).
- Name new test scripts as `test_*.py` at repo root unless a dedicated `tests/` package is introduced.
- Before opening a PR, run the affected scripts and include command/output summary in the PR description.

## Commit & Pull Request Guidelines
- Follow the existing commit style: `feat: ...`, `fix: ...`, short imperative subject line.
- Scope each commit to a single concern (UI, API, DB, integration).
- PRs should include: purpose, key file changes, manual test steps, and screenshots for `web/` UI changes.
- Reference related issue/task IDs when available.

## Security & Configuration Tips
- Do not commit secrets, real POS credentials, or production host-specific values.
- Treat JSON/config files as environment data; provide safe defaults and document required keys in PRs when adding new settings.

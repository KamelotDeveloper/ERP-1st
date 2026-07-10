# Tasks: Multi-PC LAN Support

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 500–650 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Backend → PR 2: Tauri → PR 3: Frontend |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Backend: WAL, binding, CORS, static, health | PR 1 | Standalone, testable via curl |
| 2 | Tauri: deps, mode branching, store commands | PR 2 | Depends on PR 1 for testing |
| 3 | Frontend: wizard, banner, config, dynamic API | PR 3 | Depends on PR 2 (store) |

## Phase 1: Foundation (Backend)

- [x] 1.1 `backend/database.py` — Add `@event.listens_for(engine, "connect")` with `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`
- [x] 1.2 `backend/main.py` — Migrate to lifespan context manager; add `wal_checkpoint(TRUNCATE)` on shutdown via `text()`
- [x] 1.3 `backend/main.py` — Change uvicorn host to `"0.0.0.0"` and CORS to `allow_origins=["*"]`
- [x] 1.4 `backend/main.py` — Mount `frontend/dist` as `StaticFiles` at root, conditionally if path exists
- [x] 1.5 `backend/main.py` — Enhance `GET /health` with `lan_ip`, `port`, `sharing_url`, `db` fields

## Phase 2: Core Implementation (Tauri)

- [x] 2.1 `frontend/src-tauri/Cargo.toml` — Add `tauri-plugin-store` and `local-ip-address` deps
- [x] 2.2 `frontend/src-tauri/capabilities/default.json` — Add `"store:default"` permission
- [x] 2.3 `frontend/src-tauri/tauri.conf.json` — Change CSP `connect-src` to include `http://*:*`
- [x] 2.4 `frontend/src-tauri/src/main.rs` — Init `tauri-plugin-store`, wrap backend spawn in mode check (SERVER spawns, CLIENT skips)
- [x] 2.5 `frontend/src-tauri/src/main.rs` — Add commands: `get_mode`, `set_mode`, `get_server_ip`, `set_client_ip`, `get_lan_ip`, `test_connection`; add `lan_ip` and `sharing_url` to health response

## Phase 3: Integration / Wiring (Frontend)

- [x] 3.1 `frontend/src/services/api.js` — Refactor to async init: read `server_ip` + `lan_mode` from `@tauri-apps/plugin-store`, fallback to `127.0.0.1:8000`
- [x] 3.2 Create `frontend/src/components/SetupWizard.jsx` — Full-screen first-run: "Servidor" (auto-detects LAN IP) or "Cliente" (IP input + connection test)
- [x] 3.3 Create `frontend/src/components/ServerInfo.jsx` — Dismissible banner: "Compartiendo en http://{lan_ip}:8000"
- [x] 3.4 Create `frontend/src/components/ClientConfig.jsx` — Settings page: show current IP, edit form, connection test before save, gear icon in navbar
- [x] 3.5 `frontend/src/App.jsx` — Add startup config check: if no `lan_mode` in store, render `<SetupWizard>` before `<Dashboard>`; add `/settings` route
- [x] 3.6 `frontend/src/components/Sidebar.jsx` — Add NavLink to `/settings` (gear icon)
- [x] 3.7 `frontend/src/components/Navbar.jsx` — Integrate `<ServerInfo>` banner in SERVER mode
- [x] 3.8 `frontend/src/styles.css` — Add styles for wizard, banner, settings form, connection status indicators

## Phase 4: Testing

- [x] 4.1 Test: WAL pragmas apply on SQLite connect — query `PRAGMA journal_mode` returns `"wal"`
- [x] 4.2 Test: FastAPI TestClient — `GET /health` returns `lan_ip`, `port`, `sharing_url` keys
- [x] 4.3 Test: FastAPI TestClient — CORS headers include `Access-Control-Allow-Origin: *`
- [ ] 4.4 Test: Tauri commands — `get_mode`/`set_mode` roundtrip via Store, `test_connection` health probe
- [ ] 4.5 Verify: SetupWizard renders on fresh install, redirects after role selection
- [ ] 4.6 Verify: CLIENT mode skips backend spawn (port 8000 not listening locally)

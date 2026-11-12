# DATA_CONTRACT — Sovereign Workbench persistence contract (v1)

**Contract version:** 1 · **Date:** 2026-11-13 · **Status:** ACTIVE (M1.0)
**Parties:** M1 (auth: users, sessions) · M4 (persistence: tasks, egress_events) · Integration owner: **Backend engineer** · Reviewer: Lead

## 1. Why this contract exists (M1.0)

M1 (authentication) and M4 (persistence) run **in parallel**. Without a fixed schema and interface, each would invent its own store and they would collide at integration. This document is that agreement. Both workstreams implement **against this contract**; `tests/test_data_contract.py` enforces it (executable contract).

## 2. Database facts

| Property | Value |
|---|---|
| Engine | SQLite, **WAL mode** (`PRAGMA journal_mode=WAL`) |
| File | `workspace/workbench.db` (path constant lives in `app/config.py` when M4.1 lands) |
| Migrations | Owned by **M4.1** (runner + `schema_version` table). M1 never creates/alters tables outside its ownership. |
| Writers | Single-process assumption until M6.1 (Postgres). WAL guards against reader/writer tearing, not multi-process writers. |
| Timestamps | ISO-8601 UTC strings (consistent with existing `datetime.now(timezone.utc).isoformat()` usage) |
| Structured payloads | JSON in TEXT columns, validated at the store boundary — never raw-SQL'd from other modules |
| IDs | `uuid4().hex` (matches the existing `TaskContext.id` scheme) |

## 3. Canonical DDL (v1)

The single source of schema truth. The test in §6 executes this block verbatim.

```sql
-- contract-version: 1
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (            -- owner: M1
    id            TEXT PRIMARY KEY,           -- uuid4 hex
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,              -- bcrypt only; never plaintext/recoverable
    role          TEXT NOT NULL DEFAULT 'user',  -- 'user' | 'admin'
    created_at    TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sessions (         -- owner: M1
    id          TEXT PRIMARY KEY,             -- server-side session id
    user_id     TEXT NOT NULL REFERENCES users(id),
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    revoked_at  TEXT,                         -- set on logout (server-side revocation)
    ip          TEXT,
    user_agent  TEXT
);

CREATE TABLE IF NOT EXISTS tasks (            -- owner: M4
    id           TEXT PRIMARY KEY,            -- TaskContext.id (uuid4 hex[:10])
    user_id      TEXT,                        -- ownership key (M1.2); NULL allowed in single-user v0.5
    task         TEXT NOT NULL,
    attachments  TEXT NOT NULL DEFAULT '[]',  -- JSON array of workspace-relative paths
    routing      TEXT NOT NULL DEFAULT '{}',  -- JSON RoutingDecision.to_dict()
    plan         TEXT NOT NULL DEFAULT '[]',  -- JSON array of steps
    actions      TEXT NOT NULL DEFAULT '[]',  -- JSON array (incl. "_code" for verified code)
    deliverables TEXT NOT NULL DEFAULT '[]',  -- JSON array of paths
    answer       TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'running',  -- running|completed|failed|cancelled|interrupted
    retry_of     TEXT REFERENCES tasks(id),   -- M4.2: retry = NEW task linked to the original
    started_at   TEXT NOT NULL,
    finished_at  TEXT
);

CREATE TABLE IF NOT EXISTS egress_events (    -- owner: M4
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    dest     TEXT NOT NULL,
    port     INTEGER,
    verdict  TEXT NOT NULL                     -- 'ALLOWED (loopback)' | 'BLOCKED (air-gap policy)'
);

CREATE INDEX IF NOT EXISTS idx_tasks_user   ON tasks(user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_egress_ts    ON egress_events(ts);
```

## 4. Interface signatures (implemented in `backend/app/db/`)

All persistence is accessed through these stores — **no raw SQL outside `app/db/`**.

```python
# --- M1.1 implements ---
class UserStore:
    def create(self, username: str, password_hash: str, role: str) -> str: ...
    def get_by_username(self, username: str) -> dict | None: ...
    def get(self, user_id: str) -> dict | None: ...
    def set_active(self, user_id: str, active: bool) -> None: ...
    def count(self) -> int: ...

class SessionStore:
    def create(self, user_id: str, expires_at: str, ip: str, user_agent: str) -> str: ...
    def get(self, session_id: str) -> dict | None:    # honours expiry + revocation
    def revoke(self, session_id: str) -> None: ...
    def purge_expired(self) -> int: ...

# --- M4.1 implements ---
class TaskStore:
    def save(self, ctx) -> None:                      # full TaskContext write-through
    def update_status(self, task_id: str, status: str, finished_at: str | None) -> None: ...
    def get(self, task_id: str) -> dict | None: ...
    def list(self, user_id: str | None = None, limit: int = 100) -> list[dict]: ...
    def mark_interrupted_orphans(self) -> int:        # startup reconciliation: 'running' rows → 'interrupted'

class EgressEventStore:
    def record(self, ts: str, dest: str, port: int | None, verdict: str) -> None: ...
    def recent(self, limit: int = 500) -> list[dict]: ...
    def counters(self) -> dict: ...
```

## 5. Ownership matrix

| Artifact | Owner | Notes |
|---|---|---|
| `users`, `sessions` DDL + UserStore/SessionStore | M1 (M1.1) | schema changes require contract-version bump |
| `tasks`, `egress_events` DDL + TaskStore/EgressEventStore | M4 (M4.1) | same rule |
| `schema_version` + migration runner | M4.1 | M1 depends on tables existing, never creates them |
| Integration & conflict resolution | Backend engineer | reviewed by Lead |

**Change rule:** any schema change = edit this file, bump `contract-version`, update `REQUIRED` in the test, migrate — in that order, in one commit series. The drift test fails otherwise.

## 6. Drift enforcement (executable contract)

`tests/test_data_contract.py`:
1. Extracts the ```sql block above and executes it in an in-memory SQLite — the DDL must always be runnable.
2. Asserts every table has **all** contract columns (`REQUIRED` map in the test).
3. Asserts no tables exist outside the contract (v1 set).
4. **From M4.1 onward** the same test additionally opens the live `workspace/workbench.db` (if present) and asserts every live table is a superset of its contract columns — drift fails CI, never silently ships.

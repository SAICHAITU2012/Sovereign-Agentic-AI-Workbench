"""M1.0 — executable persistence contract check.

docs/DATA_CONTRACT.md is the single schema truth shared by M1 (auth) and
M4 (persistence). This test makes the contract *executable*: the canonical
DDL must always run, contain every contract column, and contain nothing
outside the contract. From M4.1 onward the same test compares the live DB
against the contract (drift fails CI, never silently ships).
"""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MD = ROOT / "docs" / "DATA_CONTRACT.md"

# v1 contract — every table must have at least these columns.
REQUIRED = {
    "schema_version": ["version", "applied_at"],
    "users": ["id", "username", "password_hash", "role", "created_at", "is_active"],
    "sessions": ["id", "user_id", "created_at", "expires_at", "revoked_at",
                 "ip", "user_agent"],
    "tasks": ["id", "user_id", "task", "attachments", "routing", "plan",
              "actions", "deliverables", "answer", "status", "retry_of",
              "started_at", "finished_at"],
    "egress_events": ["id", "ts", "dest", "port", "verdict"],
}


def _ddl() -> str:
    text = CONTRACT_MD.read_text()
    blocks = re.findall(r"```sql\n(.*?)```", text, re.S)
    assert blocks, "DATA_CONTRACT.md lost its ```sql block — contract is unenforceable"
    return blocks[0]


def _apply(ddl: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(ddl)
    return conn


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows} - {"sqlite_sequence"}  # AUTOINCREMENT bookkeeping


def test_contract_ddl_is_executable():
    ddl = _ddl()
    assert "contract-version: 1" in ddl, "DDL block must carry its contract version"
    _apply(ddl)  # raises if the DDL drifted into something non-executable


def test_contract_tables_have_all_required_columns():
    conn = _apply(_ddl())
    for table, cols in REQUIRED.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        missing = [c for c in cols if c not in have]
        assert not missing, f"contract drift: {table} missing {missing}"


def test_contract_defines_exactly_the_v1_tables():
    conn = _apply(_ddl())
    extra = _tables(conn) - set(REQUIRED)
    assert not extra, f"tables outside the contract (bump contract-version first): {extra}"


def test_live_database_matches_contract():
    """Active from M4.1 onward: any existing live DB must be a column
    superset of the contract. Skips silently while only the DDL exists."""
    live_db = ROOT / "workspace" / "workbench.db"
    if not live_db.exists():
        return  # M4.1 hasn't run yet — nothing to check
    live = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True)
    for table, cols in REQUIRED.items():
        have = {r[1] for r in live.execute(f"PRAGMA table_info({table})")}
        if not have:
            continue  # table not migrated yet in this DB
        missing = [c for c in cols if c not in have]
        assert not missing, f"LIVE DB DRIFT: {table} missing contract columns {missing}"

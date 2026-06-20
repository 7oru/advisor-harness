"""SQLite persistence for advisor harness runs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from packages.harness.artifacts import utc_now


DB_RELATIVE_PATH = Path("memory") / "advisor_runs.db"
SCHEMA_VERSION = 1


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    task TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    executor_backend TEXT NOT NULL,
    advisor_backend TEXT NOT NULL,
    executor_session_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    max_turns INTEGER NOT NULL,
    max_advisor_calls INTEGER NOT NULL,
    executor_turn_count INTEGER NOT NULL DEFAULT 0,
    advisor_consult_count INTEGER NOT NULL DEFAULT 0,
    advisor_guidance_count INTEGER NOT NULL DEFAULT 0,
    memory_proposal_count INTEGER NOT NULL DEFAULT 0,
    malformed_block_count INTEGER NOT NULL DEFAULT 0,
    error_mode TEXT NOT NULL DEFAULT 'none',
    executor_done_json TEXT NOT NULL DEFAULT '{}',
    outcome_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_executor_backend ON runs(executor_backend);
CREATE INDEX IF NOT EXISTS idx_runs_advisor_backend ON runs(advisor_backend);
CREATE INDEX IF NOT EXISTS idx_runs_advisor_consults ON runs(advisor_consult_count);
CREATE INDEX IF NOT EXISTS idx_runs_error_mode ON runs(error_mode);
CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task);

CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    turn INTEGER,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_events_run_order ON session_events(run_id, id);
CREATE INDEX IF NOT EXISTS idx_session_events_type ON session_events(event_type);

CREATE TABLE IF NOT EXISTS agent_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('executor', 'advisor', 'review')),
    turn INTEGER NOT NULL,
    exit_code INTEGER NOT NULL,
    prompt_text TEXT NOT NULL DEFAULT '',
    final_message TEXT NOT NULL DEFAULT '',
    stdout_text TEXT NOT NULL DEFAULT '',
    stderr_text TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '{}',
    prompt_path TEXT NOT NULL DEFAULT '',
    stdout_path TEXT NOT NULL DEFAULT '',
    stderr_path TEXT NOT NULL DEFAULT '',
    raw_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(run_id, role, turn),
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_turns_run_role ON agent_turns(run_id, role, turn);

CREATE TABLE IF NOT EXISTS advisor_consults (
    consult_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    question TEXT NOT NULL,
    context TEXT NOT NULL,
    options_json TEXT NOT NULL DEFAULT '[]',
    preferred_option TEXT NOT NULL DEFAULT '',
    urgency TEXT NOT NULL DEFAULT 'normal',
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_advisor_consults_run_turn ON advisor_consults(run_id, turn);

CREATE TABLE IF NOT EXISTS advisor_guidance (
    guidance_id TEXT PRIMARY KEY,
    consult_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    guidance TEXT NOT NULL,
    rationale TEXT NOT NULL,
    stop_signal INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY(consult_id) REFERENCES advisor_consults(consult_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_advisor_guidance_run_turn ON advisor_guidance(run_id, turn);

CREATE TABLE IF NOT EXISTS memory_proposals (
    proposal_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    source_excerpt TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    expires_at TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_memory_proposals_run ON memory_proposals(run_id);

CREATE TABLE IF NOT EXISTS malformed_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    tag TEXT NOT NULL,
    error TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_malformed_blocks_run ON malformed_blocks(run_id);
"""


def database_path(root: Path) -> Path:
    """Return the default SQLite database path for a workspace."""
    return root / DB_RELATIVE_PATH


class RunDatabase:
    """Small repository for queryable run state."""

    def __init__(self, path: Path):
        self.path = path

    @classmethod
    def for_root(cls, root: Path) -> "RunDatabase":
        return cls(database_path(root))

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, utc_now()),
            )

    def record_run_started(
        self,
        *,
        run_id: str,
        task: str,
        executor_backend: str,
        advisor_backend: str,
        executor_session_id: str,
        max_turns: int,
        max_advisor_calls: int,
        created_at: Optional[str] = None,
    ) -> None:
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, task, status, executor_backend, advisor_backend,
                    executor_session_id, created_at, max_turns, max_advisor_calls
                )
                VALUES (?, ?, 'running', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    task=excluded.task,
                    executor_backend=excluded.executor_backend,
                    advisor_backend=excluded.advisor_backend,
                    executor_session_id=excluded.executor_session_id,
                    max_turns=excluded.max_turns,
                    max_advisor_calls=excluded.max_advisor_calls
                """,
                (
                    run_id,
                    task,
                    executor_backend,
                    advisor_backend,
                    executor_session_id,
                    created_at or utc_now(),
                    int(max_turns),
                    int(max_advisor_calls),
                ),
            )

    def record_session_event(self, run_id: str, event: Dict[str, Any]) -> None:
        self.initialize()
        payload = dict(event)
        event_type = str(payload.get("type") or "event")
        created_at = str(payload.get("created_at") or utc_now())
        payload.setdefault("created_at", created_at)
        turn = _optional_int(payload.get("turn"))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_events(run_id, event_type, turn, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, event_type, turn, created_at, _json_dumps(payload)),
            )

    def record_agent_turn(
        self,
        *,
        run_id: str,
        role: str,
        turn: int,
        exit_code: int,
        prompt_text: str = "",
        final_message: str = "",
        stdout_text: str = "",
        stderr_text: str = "",
        raw_payload: Optional[Dict[str, Any]] = None,
        prompt_path: str = "",
        stdout_path: str = "",
        stderr_path: str = "",
        raw_path: str = "",
        created_at: Optional[str] = None,
    ) -> None:
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_turns (
                    run_id, role, turn, exit_code, prompt_text, final_message,
                    stdout_text, stderr_text, raw_json, prompt_path, stdout_path,
                    stderr_path, raw_path, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, role, turn) DO UPDATE SET
                    exit_code=excluded.exit_code,
                    prompt_text=excluded.prompt_text,
                    final_message=excluded.final_message,
                    stdout_text=excluded.stdout_text,
                    stderr_text=excluded.stderr_text,
                    raw_json=excluded.raw_json,
                    prompt_path=excluded.prompt_path,
                    stdout_path=excluded.stdout_path,
                    stderr_path=excluded.stderr_path,
                    raw_path=excluded.raw_path,
                    created_at=excluded.created_at
                """,
                (
                    run_id,
                    role,
                    int(turn),
                    int(exit_code),
                    prompt_text,
                    final_message,
                    stdout_text,
                    stderr_text,
                    _json_dumps(raw_payload or {}),
                    prompt_path,
                    stdout_path,
                    stderr_path,
                    raw_path,
                    created_at or utc_now(),
                ),
            )

    def record_advisor_consult(self, consult: Dict[str, Any]) -> None:
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO advisor_consults (
                    consult_id, run_id, turn, question, context, options_json,
                    preferred_option, urgency, created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(consult_id) DO UPDATE SET
                    run_id=excluded.run_id,
                    turn=excluded.turn,
                    question=excluded.question,
                    context=excluded.context,
                    options_json=excluded.options_json,
                    preferred_option=excluded.preferred_option,
                    urgency=excluded.urgency,
                    created_at=excluded.created_at,
                    payload_json=excluded.payload_json
                """,
                (
                    consult["id"],
                    consult["run_id"],
                    int(consult.get("turn") or 0),
                    str(consult.get("question") or ""),
                    str(consult.get("context") or ""),
                    _json_dumps(consult.get("options") or []),
                    str(consult.get("preferred_option") or ""),
                    str(consult.get("urgency") or "normal"),
                    str(consult.get("created_at") or utc_now()),
                    _json_dumps(consult),
                ),
            )

    def record_advisor_guidance(self, *, run_id: str, turn: int, guidance: Dict[str, Any]) -> None:
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO advisor_guidance (
                    guidance_id, consult_id, run_id, turn, guidance, rationale,
                    stop_signal, created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guidance_id) DO UPDATE SET
                    consult_id=excluded.consult_id,
                    run_id=excluded.run_id,
                    turn=excluded.turn,
                    guidance=excluded.guidance,
                    rationale=excluded.rationale,
                    stop_signal=excluded.stop_signal,
                    created_at=excluded.created_at,
                    payload_json=excluded.payload_json
                """,
                (
                    guidance["id"],
                    guidance["consult_id"],
                    run_id,
                    int(turn),
                    str(guidance.get("guidance") or ""),
                    str(guidance.get("rationale") or ""),
                    1 if guidance.get("stop_signal") else 0,
                    str(guidance.get("created_at") or utc_now()),
                    _json_dumps(guidance),
                ),
            )

    def record_memory_proposal(self, proposal: Dict[str, Any]) -> None:
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_proposals (
                    proposal_id, run_id, type, content, source_excerpt, confidence,
                    expires_at, tags_json, created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    run_id=excluded.run_id,
                    type=excluded.type,
                    content=excluded.content,
                    source_excerpt=excluded.source_excerpt,
                    confidence=excluded.confidence,
                    expires_at=excluded.expires_at,
                    tags_json=excluded.tags_json,
                    created_at=excluded.created_at,
                    payload_json=excluded.payload_json
                """,
                (
                    proposal["id"],
                    proposal["run_id"],
                    str(proposal.get("type") or "episode"),
                    str(proposal.get("content") or ""),
                    str(proposal.get("source_excerpt") or ""),
                    float(proposal.get("confidence") or 0.0),
                    proposal.get("expires_at"),
                    _json_dumps(proposal.get("tags") or []),
                    str(proposal.get("created_at") or utc_now()),
                    _json_dumps(proposal),
                ),
            )

    def record_malformed_block(self, *, run_id: str, turn: int, block: Dict[str, Any]) -> None:
        self.initialize()
        payload = dict(block)
        payload.setdefault("created_at", utc_now())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO malformed_blocks(run_id, turn, tag, error, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    int(turn),
                    str(payload.get("tag") or ""),
                    str(payload.get("error") or ""),
                    str(payload["created_at"]),
                    _json_dumps(payload),
                ),
            )

    def record_outcome(self, outcome: Dict[str, Any]) -> None:
        self.initialize()
        run_id = str(outcome["run_id"])
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs SET
                    status=?,
                    completed_at=?,
                    executor_turn_count=?,
                    advisor_consult_count=?,
                    advisor_guidance_count=?,
                    memory_proposal_count=?,
                    malformed_block_count=?,
                    error_mode=?,
                    executor_done_json=?,
                    outcome_json=?
                WHERE run_id=?
                """,
                (
                    str(outcome.get("status") or "unknown"),
                    str(outcome.get("completed_at") or utc_now()),
                    int(outcome.get("executor_turn_count") or 0),
                    int(outcome.get("advisor_consult_count") or 0),
                    int(outcome.get("advisor_guidance_count") or 0),
                    int(outcome.get("memory_proposal_count") or 0),
                    int(outcome.get("malformed_block_count") or 0),
                    _error_mode(outcome),
                    _json_dumps(outcome.get("executor_done") or {}),
                    _json_dumps(outcome),
                    run_id,
                ),
            )

    def list_runs(
        self,
        *,
        status: Optional[str] = None,
        backend: Optional[str] = None,
        advisor_call_count: Optional[int] = None,
        task: Optional[str] = None,
        error_mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self.initialize()
        clauses: List[str] = []
        params: List[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if backend:
            clauses.append("(executor_backend = ? OR advisor_backend = ?)")
            params.extend([backend, backend])
        if advisor_call_count is not None:
            clauses.append("advisor_consult_count = ?")
            params.append(int(advisor_call_count))
        if task:
            clauses.append("LOWER(task) LIKE ?")
            params.append("%{}%".format(task.lower()))
        if error_mode:
            clauses.append("error_mode = ?")
            params.append(error_mode)
        query = "SELECT * FROM runs"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC, run_id DESC"
        with self._connect() as conn:
            return [_run_row_to_dict(row) for row in conn.execute(query, params).fetchall()]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _run_row_to_dict(row) if row else None

    def get_session_events(self, run_id: str) -> List[Dict[str, Any]]:
        return self._fetch_payload_rows(
            "SELECT * FROM session_events WHERE run_id = ? ORDER BY id",
            (run_id,),
            payload_column="payload_json",
        )

    def get_agent_turns(self, run_id: str) -> List[Dict[str, Any]]:
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_turns WHERE run_id = ? ORDER BY turn, role",
                (run_id,),
            ).fetchall()
        return [_row_with_json(row, json_columns=("raw_json",)) for row in rows]

    def get_advisor_consults(self, run_id: str) -> List[Dict[str, Any]]:
        return self._fetch_payload_rows(
            "SELECT * FROM advisor_consults WHERE run_id = ? ORDER BY turn, created_at",
            (run_id,),
            payload_column="payload_json",
        )

    def get_advisor_guidance(self, run_id: str) -> List[Dict[str, Any]]:
        return self._fetch_payload_rows(
            "SELECT * FROM advisor_guidance WHERE run_id = ? ORDER BY turn, created_at",
            (run_id,),
            payload_column="payload_json",
        )

    def get_memory_proposals(self, run_id: str) -> List[Dict[str, Any]]:
        return self._fetch_payload_rows(
            "SELECT * FROM memory_proposals WHERE run_id = ? ORDER BY created_at",
            (run_id,),
            payload_column="payload_json",
        )

    def get_malformed_blocks(self, run_id: str) -> List[Dict[str, Any]]:
        return self._fetch_payload_rows(
            "SELECT * FROM malformed_blocks WHERE run_id = ? ORDER BY id",
            (run_id,),
            payload_column="payload_json",
        )

    def run_payload(self, run_id: str) -> Dict[str, Any]:
        """Return the full payload needed by the local UI."""
        run = self.get_run(run_id)
        if not run:
            raise FileNotFoundError("run not found in database: {}".format(run_id))
        return {
            "run": run,
            "events": self.get_session_events(run_id),
            "agent_turns": self.get_agent_turns(run_id),
            "advisor_consults": self.get_advisor_consults(run_id),
            "advisor_guidance": self.get_advisor_guidance(run_id),
            "memory_proposals": self.get_memory_proposals(run_id),
            "malformed_blocks": self.get_malformed_blocks(run_id),
        }

    def _fetch_payload_rows(
        self,
        query: str,
        params: Sequence[Any],
        *,
        payload_column: str,
    ) -> List[Dict[str, Any]]:
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_payload_row(row, payload_column=payload_column) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def _payload_row(row: sqlite3.Row, *, payload_column: str) -> Dict[str, Any]:
    payload = _json_loads(row[payload_column], fallback={})
    if not isinstance(payload, dict):
        payload = {"value": payload}
    for key in row.keys():
        if key == payload_column:
            continue
        payload.setdefault(key, row[key])
    return payload


def _run_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = _row_with_json(row, json_columns=("executor_done_json", "outcome_json"))
    data["executor_done"] = data.pop("executor_done_json")
    data["outcome"] = data.pop("outcome_json")
    return data


def _row_with_json(row: sqlite3.Row, *, json_columns: Iterable[str]) -> Dict[str, Any]:
    data = dict(row)
    for key in json_columns:
        data[key] = _json_loads(str(data.get(key) or ""), fallback={})
    return data


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _json_loads(value: str, *, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _error_mode(outcome: Dict[str, Any]) -> str:
    malformed_blocks = outcome.get("malformed_blocks") or []
    if malformed_blocks:
        first = malformed_blocks[0]
        if isinstance(first, dict):
            tag = first.get("tag") or "unknown"
            return "malformed:{}".format(tag)
        return "malformed:unknown"
    status = str(outcome.get("status") or "unknown")
    return "none" if status == "completed" else status

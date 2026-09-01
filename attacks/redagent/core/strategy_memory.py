"""
Strategy Memory — SQLite persistence for the co-evolution loop.

The red agent's long-term memory: every campaign's plan, the blue team's
detection outcome, per-round confusion matrices, and the SHAP-derived
"why caught" notes. Feeds the mutation loop (caught patterns avoided,
missed patterns amplified) and the Robustness Ledger.

Schema:
  campaigns(id, ts, vector, rail_profile, plan_json, n_txns, n_dropped,
            detected, detection_rate, evasion_notes)
  rounds(id, ts, campaign_id, blue_version, tp, fp, fn, tn, f1, notes)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SENSITIVE_ROOTS = tuple(Path(r) for r in ("/etc", "/sys", "/proc", "/dev", "/boot"))


def _validate_db_path(path: str | Path) -> Path:
    """Basic sanity check on a caller/env-supplied sqlite path (LIVEFIRE_DB):
    reject directories and refuse to write inside an OS-sensitive root."""
    p = Path(path).resolve()
    if p.exists() and p.is_dir():
        raise ValueError(f"LIVEFIRE_DB points at a directory, not a file: {p}")
    if any(p == root or root in p.parents for root in _SENSITIVE_ROOTS):
        raise ValueError(f"LIVEFIRE_DB refuses to write inside a system directory: {p}")
    return p


_DEFAULT_DB = _validate_db_path(os.environ.get(
    "LIVEFIRE_DB", Path(__file__).resolve().parents[3] / "arena_ledger.db"))


class StrategyMemory:
    def __init__(self, db_path: str | Path | None = None):
        self._path = str(_validate_db_path(db_path) if db_path else _DEFAULT_DB)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # PRAGMA foreign_keys=ON is intentionally NOT set here: run_tournament()
        # (arena/loop.py) calls record_round() with a synthetic aggregate
        # campaign_id ("{profile}_g{gen}_tournament") that is never inserted via
        # record_campaign() -- enforcing the FK makes every tournament round raise
        # sqlite3.IntegrityError. Fix belongs in arena/loop.py's run_tournament
        # (insert a matching campaign row for the aggregate id, or stop treating
        # rounds.campaign_id as a hard FK), not here.
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    vector TEXT NOT NULL,
                    rail_profile TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    n_txns INTEGER NOT NULL,
                    n_dropped INTEGER NOT NULL,
                    detected INTEGER NOT NULL,
                    detection_rate REAL NOT NULL,
                    evasion_notes TEXT
                );
                CREATE TABLE IF NOT EXISTS rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    blue_version TEXT NOT NULL,
                    tp INTEGER, fp INTEGER, fn INTEGER, tn INTEGER,
                    f1 REAL,
                    notes TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
                );
                CREATE INDEX IF NOT EXISTS idx_campaigns_vector ON campaigns(vector);
                CREATE INDEX IF NOT EXISTS idx_rounds_campaign ON rounds(campaign_id);
                """
            )
            self._conn.commit()

    # ------------------------------------------------------------ writes

    def record_campaign(
        self,
        *,
        campaign_id: str,
        vector: str,
        rail_profile: str,
        plan: dict[str, Any],
        n_txns: int,
        n_dropped: int,
        detection_rate: float,
        evasion_notes: str = "",
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO campaigns VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    campaign_id, datetime.now(timezone.utc).isoformat(), vector,
                    rail_profile, json.dumps(plan), n_txns, n_dropped,
                    int(detection_rate < 1.0), round(float(detection_rate), 4),
                    evasion_notes,
                ),
            )
            self._conn.commit()

    def record_round(
        self, *, campaign_id: str, blue_version: str,
        tp: int, fp: int, fn: int, tn: int, f1: float, notes: str = "",
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO rounds(ts, campaign_id, blue_version, tp, fp, fn, tn, f1, notes) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), campaign_id, blue_version,
                 tp, fp, fn, tn, round(float(f1), 4), notes),
            )
            self._conn.commit()

    # ------------------------------------------------------------ queries

    def vector_stats(self) -> list[dict[str, Any]]:
        """Per-vector: attempts, mean detection rate — the red agent's report card."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT vector, COUNT(*) AS attempts, AVG(detection_rate) AS avg_detection, "
                "SUM(detected) AS times_caught, MAX(ts) AS last_seen "
                "FROM campaigns GROUP BY vector ORDER BY attempts DESC"
            )
            return [dict(r) for r in cur.fetchall()]

    def caught_plans(self, limit: int = 20) -> list[dict[str, Any]]:
        """Recently caught plans (detection_rate high) — mutation fuel."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM campaigns WHERE detection_rate >= 0.5 "
                "ORDER BY ts DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def evaded_plans(self, limit: int = 20) -> list[dict[str, Any]]:
        """Successful evasions — the red agent's trophy shelf."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM campaigns WHERE detection_rate < 0.1 "
                "ORDER BY ts DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def ledger(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM campaigns ORDER BY ts DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def round_history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM rounds ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        m = StrategyMemory(Path(td) / "test.db")
        m.record_campaign(campaign_id="c1", vector="card_testing", rail_profile="us_cnp",
                          plan={"vector": "card_testing"}, n_txns=100, n_dropped=2,
                          detection_rate=0.9, evasion_notes="caught by velocity")
        m.record_campaign(campaign_id="c2", vector="mule_layering", rail_profile="card_intl",
                          plan={"vector": "mule_layering"}, n_txns=50, n_dropped=0,
                          detection_rate=0.04, evasion_notes="dispersed below thresholds")
        m.record_round(campaign_id="c1", blue_version="bb_v1", tp=88, fp=5, fn=10, tn=8997, f1=0.92)
        assert len(m.vector_stats()) == 2
        assert len(m.caught_plans()) == 1 and m.caught_plans()[0]["vector"] == "card_testing"
        assert len(m.evaded_plans()) == 1 and m.evaded_plans()[0]["vector"] == "mule_layering"
        assert len(m.ledger()) == 2 and len(m.round_history()) == 1
        m.close()
    print("[OK] strategy memory selftest passed")



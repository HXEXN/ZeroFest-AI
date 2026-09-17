"""SQLite synchronization hardening for the ZeroFest Streamlit demo.

This module patches services.database at package import time.

Goals:
- use WAL mode for concurrent readers + one writer
- wait on short write contention instead of failing immediately
- keep demo reset transactional (never unlink the live DB file)
- expose a monotonically increasing runtime revision for live UI diagnostics
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Iterator


SERVER_INSTANCE_ID = uuid.uuid4().hex[:10]


TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS zf_rev_sales_insert
AFTER INSERT ON sales_snapshots
BEGIN
    UPDATE settings
    SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
    WHERE key = 'runtime_revision';
END;

CREATE TRIGGER IF NOT EXISTS zf_rev_inventory_insert
AFTER INSERT ON inventory_snapshots
BEGIN
    UPDATE settings
    SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
    WHERE key = 'runtime_revision';
END;

CREATE TRIGGER IF NOT EXISTS zf_rev_prediction_insert
AFTER INSERT ON predictions
BEGIN
    UPDATE settings
    SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
    WHERE key = 'runtime_revision';
END;

CREATE TRIGGER IF NOT EXISTS zf_rev_action_insert
AFTER INSERT ON agent_actions
BEGIN
    UPDATE settings
    SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
    WHERE key = 'runtime_revision';
END;

CREATE TRIGGER IF NOT EXISTS zf_rev_action_update
AFTER UPDATE ON agent_actions
BEGIN
    UPDATE settings
    SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
    WHERE key = 'runtime_revision';
END;

CREATE TRIGGER IF NOT EXISTS zf_rev_promotion_insert
AFTER INSERT ON promotions
BEGIN
    UPDATE settings
    SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
    WHERE key = 'runtime_revision';
END;

CREATE TRIGGER IF NOT EXISTS zf_rev_promotion_update
AFTER UPDATE ON promotions
BEGIN
    UPDATE settings
    SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
    WHERE key = 'runtime_revision';
END;

CREATE TRIGGER IF NOT EXISTS zf_rev_settings_insert
AFTER INSERT ON settings
WHEN NEW.key <> 'runtime_revision'
BEGIN
    UPDATE settings
    SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
    WHERE key = 'runtime_revision';
END;

CREATE TRIGGER IF NOT EXISTS zf_rev_settings_update
AFTER UPDATE ON settings
WHEN NEW.key <> 'runtime_revision'
BEGIN
    UPDATE settings
    SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
    WHERE key = 'runtime_revision';
END;
"""


def install_sqlite_sync(db: ModuleType) -> None:
    """Patch the already imported services.database module once."""
    if getattr(db, "_SQLITE_SYNC_PATCHED", False):
        return

    original_initialize_database = db.initialize_database

    def _enable_wal(db_path: Path | str) -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            str(path),
            timeout=30,
            check_same_thread=False,
        )
        try:
            conn.execute("PRAGMA busy_timeout = 15000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA wal_autocheckpoint = 1000")
        finally:
            conn.close()

    @contextmanager
    def synced_connection(
        db_path: Path | str = db.DB_PATH,
    ) -> Iterator[sqlite3.Connection]:
        """Open a fresh connection that always sees the latest committed state."""
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            str(path),
            timeout=30,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA synchronous = NORMAL")

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Existing functions in database.py resolve `connection` at call time,
    # therefore replacing the module global upgrades all reads/writes at once.
    db.connection = synced_connection

    def _install_runtime_metadata(db_path: Path | str) -> None:
        with synced_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value)
                VALUES ('runtime_revision', '1')
                ON CONFLICT(key) DO NOTHING
                """
            )
            conn.executescript(TRIGGER_SQL)

    def initialize_database(
        db_path: Path | str = db.DB_PATH,
    ) -> None:
        _enable_wal(db_path)
        original_initialize_database(db_path)
        _install_runtime_metadata(db_path)

    def get_runtime_revision(
        db_path: Path | str = db.DB_PATH,
    ) -> int:
        row = db.query_one(
            "SELECT value FROM settings WHERE key='runtime_revision'",
            db_path=db_path,
        )
        if not row:
            return 0
        try:
            return int(row["value"])
        except (TypeError, ValueError):
            return 0

    def sqlite_sync_status(
        db_path: Path | str = db.DB_PATH,
    ) -> dict[str, object]:
        path = Path(db_path)
        with synced_connection(path) as conn:
            journal_mode = str(
                conn.execute("PRAGMA journal_mode").fetchone()[0]
            )
            busy_timeout = int(
                conn.execute("PRAGMA busy_timeout").fetchone()[0]
            )

        return {
            "db_path": str(path.resolve()),
            "journal_mode": journal_mode,
            "busy_timeout_ms": busy_timeout,
            "runtime_revision": get_runtime_revision(path),
            "server_instance_id": SERVER_INSTANCE_ID,
        }

    def _seed_demo_in_transaction(
        conn: sqlite3.Connection,
    ) -> None:
        """Seed the same deterministic demo state without opening another DB connection."""
        conn.execute(
            "INSERT INTO universities VALUES (?, ?, ?, ?)",
            ("univ-zero", "제로대학교", "서울", 15000),
        )

        conn.execute(
            "INSERT INTO festivals VALUES (?, ?, ?, ?, ?, ?)",
            (
                "festival-2026",
                "univ-zero",
                "2026 Zero Festival",
                "2026-05-22",
                "16:00",
                "22:00",
            ),
        )

        booths = [
            (
                "booth-chicken",
                "festival-2026",
                "청춘 닭꼬치",
                "A",
                37.001,
                127.001,
            ),
            (
                "booth-drink",
                "festival-2026",
                "파도 음료",
                "B",
                37.002,
                127.003,
            ),
            (
                "booth-tteok",
                "festival-2026",
                "응원단 떡볶이",
                "C",
                37.000,
                127.004,
            ),
            (
                "booth-waffle",
                "festival-2026",
                "와플 연구소",
                "B",
                37.003,
                127.002,
            ),
        ]
        conn.executemany(
            "INSERT INTO booths VALUES (?, ?, ?, ?, ?, ?)",
            booths,
        )

        menus = [
            (
                "menu-chicken",
                "booth-chicken",
                "닭꼬치",
                "food",
                6000,
                300,
            ),
            (
                "menu-drink",
                "booth-drink",
                "레몬 에이드",
                "drink",
                3000,
                157,
            ),
            (
                "menu-tteok",
                "booth-tteok",
                "떡볶이",
                "food",
                5000,
                161,
            ),
            (
                "menu-waffle",
                "booth-waffle",
                "초코 와플",
                "dessert",
                4000,
                108,
            ),
        ]
        conn.executemany(
            "INSERT INTO menus VALUES (?, ?, ?, ?, ?, ?)",
            menus,
        )

        for row in db._read_csv("sample_inventory.csv"):
            conn.execute(
                """
                INSERT INTO inventory_snapshots
                (timestamp, booth_id, menu_id, current_stock, additional_stock)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["timestamp"],
                    row["booth_id"],
                    row["menu_id"],
                    int(row["current_stock"]),
                    int(row["additional_stock"]),
                ),
            )

        for row in db._read_csv("sample_sales.csv"):
            conn.execute(
                """
                INSERT INTO sales_snapshots
                (timestamp, booth_id, menu_id, sales_quantity, revenue, ticket_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["timestamp"],
                    row["booth_id"],
                    row["menu_id"],
                    int(row["sales_quantity"]),
                    int(row["revenue"]),
                    int(row["ticket_count"]),
                ),
            )

        for row in db._read_csv("sample_weather.csv"):
            conn.execute(
                "INSERT INTO weather VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["timestamp"],
                    float(row["temperature"]),
                    float(row["precipitation_probability"]),
                    float(row["rainfall"]),
                    float(row["humidity"]),
                    row["provider"],
                ),
            )

        for row in db._read_csv("sample_events.csv"):
            conn.execute(
                "INSERT INTO festival_events VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["event_id"],
                    row["event_name"],
                    row["zone"],
                    row["start_time"],
                    row["end_time"],
                    int(row["expected_crowd"]),
                ),
            )

        historical_rows = len(
            db._read_csv("final_training_dataset.csv")
        )
        conn.execute(
            """
            INSERT INTO data_sources
            (source_id, source_name, source_type, period, row_count,
             status, data_class, last_validated_at)
            VALUES (
                'history-sample',
                'Cross-campus Festival History',
                'CSV',
                '2023–2025',
                ?,
                'READY',
                'SAMPLE / SYNTHETIC',
                ?
            )
            """,
            (
                historical_rows,
                db.DEMO_TIME,
            ),
        )

        # runtime_revision is inserted last so seed inserts do not matter.
        settings = {
            "demo_time": db.DEMO_TIME,
            "demo_mode": "1",
            "student_response_simulated": "0",
            "student_response_booth": "booth-chicken",
            "festival_total_days": "3",
            "data_disclaimer": "Sample / Synthetic Festival Dataset",
            "active_booth_id": "booth-chicken",
            "runtime_revision": "1",
        }
        conn.executemany(
            "INSERT INTO settings(key, value) VALUES (?, ?)",
            settings.items(),
        )

    def reset_demo(
        db_path: Path | str = db.DB_PATH,
    ) -> None:
        """Reset demo state atomically without deleting the live SQLite file."""
        path = Path(db_path)

        # Make sure schema, WAL mode and triggers exist first.
        initialize_database(path)

        with synced_connection(path) as conn:
            # IMMEDIATE reserves the write transaction up-front and lets WAL
            # readers keep seeing the previous consistent snapshot until commit.
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("PRAGMA defer_foreign_keys = ON")

            for table in (
                "reward_progress",
                "promotions",
                "agent_actions",
                "predictions",
                "sales_snapshots",
                "inventory_snapshots",
                "weather",
                "festival_events",
                "ml_runs",
                "data_sources",
                "menus",
                "booths",
                "festivals",
                "universities",
                "settings",
            ):
                conn.execute(f"DELETE FROM {table}")

            try:
                conn.execute("DELETE FROM sqlite_sequence")
            except sqlite3.OperationalError:
                pass

            _seed_demo_in_transaction(conn)

    def publish_pos_sync_event(
        event_type: str,
        booth_id: str,
        *,
        quantity: int | None = None,
        db_path: Path | str = db.DB_PATH,
    ) -> dict[str, object]:
        """Persist a compact POS event that Simulation can verify independently."""
        state = db.get_booth_state(booth_id, db_path)
        prediction = db.get_latest_prediction(booth_id, db_path) or {}

        revision_before_event = get_runtime_revision(db_path)
        event: dict[str, object] = {
            "event_id": uuid.uuid4().hex[:10],
            "event_type": event_type,
            "booth_id": booth_id,
            "quantity": quantity,
            "total_sales": int(state.get("total_sales") or 0),
            "current_stock": int(state.get("current_stock") or 0),
            "recent_sales_30m": int(state.get("recent_sales_30m") or 0),
            "predicted_sales_30m": int(prediction.get("predicted_sales_30m") or 0),
            "expected_remaining": int(prediction.get("expected_remaining") or 0),
            "revision_before_event": revision_before_event,
            "demo_time": db.get_demo_time(db_path).isoformat(timespec="seconds"),
            "server_instance_id": SERVER_INSTANCE_ID,
        }

        # This setting write is itself revision-tracked by the trigger.
        db.set_setting(
            "last_pos_sync_event",
            json.dumps(event, ensure_ascii=False),
            db_path,
        )
        event["revision_after_event"] = get_runtime_revision(db_path)
        return event

    def get_last_pos_sync_event(
        db_path: Path | str = db.DB_PATH,
    ) -> dict[str, object] | None:
        raw = db.get_setting("last_pos_sync_event", "", db_path)
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    def verify_pos_sim_sync(
        booth_id: str,
        db_path: Path | str = db.DB_PATH,
    ) -> dict[str, object]:
        """Compare the last POS write marker with the current Simulation-visible state."""
        status = sqlite_sync_status(db_path)
        event = get_last_pos_sync_event(db_path)
        state = db.get_booth_state(booth_id, db_path)
        prediction = db.get_latest_prediction(booth_id, db_path) or {}

        wal_ok = str(status.get("journal_mode", "")).lower() == "wal"
        revision = int(status.get("runtime_revision") or 0)

        event_seen = bool(event)
        same_booth = bool(event) and event.get("booth_id") == booth_id
        revision_ok = (
            bool(event)
            and revision > int(event.get("revision_before_event") or -1)
        )

        state_ok = False
        prediction_ok = False
        if event and same_booth:
            event_type = str(event.get("event_type") or "")
            event_sales = int(event.get("total_sales") or 0)
            event_stock = int(event.get("current_stock") or 0)
            current_sales = int(state.get("total_sales") or 0)
            current_stock = int(state.get("current_stock") or 0)

            if event_type == "sale":
                # Later student-response sales may advance the world further.
                state_ok = (
                    current_sales >= event_sales
                    and current_stock <= event_stock
                )
            elif event_type in {"stock_minus", "stock_plus", "stock_set"}:
                # A later event may move stock again, but never before the marker revision.
                state_ok = revision_ok
            else:
                state_ok = revision_ok

            # Prediction is regenerated on POS write. Later re-prediction is also valid.
            prediction_ok = bool(prediction) and revision_ok

        sync_ok = bool(
            wal_ok
            and event_seen
            and same_booth
            and revision_ok
            and state_ok
            and prediction_ok
        )

        return {
            "sync_ok": sync_ok,
            "wal_ok": wal_ok,
            "event_seen": event_seen,
            "same_booth": same_booth,
            "revision_ok": revision_ok,
            "state_ok": state_ok,
            "prediction_ok": prediction_ok,
            "runtime_revision": revision,
            "server_instance_id": status.get("server_instance_id"),
            "journal_mode": status.get("journal_mode"),
            "busy_timeout_ms": status.get("busy_timeout_ms"),
            "event": event,
            "state": state,
            "prediction": prediction,
        }

    db.initialize_database = initialize_database
    db.reset_demo = reset_demo
    db.get_runtime_revision = get_runtime_revision
    db.sqlite_sync_status = sqlite_sync_status
    db.publish_pos_sync_event = publish_pos_sync_event
    db.get_last_pos_sync_event = get_last_pos_sync_event
    db.verify_pos_sim_sync = verify_pos_sim_sync
    db._SQLITE_SYNC_PATCHED = True

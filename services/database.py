"""SQLite persistence and deterministic demo seed data."""

from __future__ import annotations

import csv
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from config import DATA_DIR, DB_PATH, DEMO_TIME


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS universities (
    university_id TEXT PRIMARY KEY,
    university_name TEXT NOT NULL,
    region TEXT NOT NULL,
    student_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS festivals (
    festival_id TEXT PRIMARY KEY,
    university_id TEXT NOT NULL REFERENCES universities(university_id),
    festival_name TEXT NOT NULL,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS booths (
    booth_id TEXT PRIMARY KEY,
    festival_id TEXT NOT NULL REFERENCES festivals(festival_id),
    booth_name TEXT NOT NULL,
    zone TEXT NOT NULL,
    latitude REAL,
    longitude REAL
);
CREATE TABLE IF NOT EXISTS menus (
    menu_id TEXT PRIMARY KEY,
    booth_id TEXT NOT NULL REFERENCES booths(booth_id),
    menu_name TEXT NOT NULL,
    category TEXT NOT NULL,
    price INTEGER NOT NULL,
    initial_stock INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    booth_id TEXT NOT NULL REFERENCES booths(booth_id),
    menu_id TEXT NOT NULL REFERENCES menus(menu_id),
    current_stock INTEGER NOT NULL,
    additional_stock INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sales_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    booth_id TEXT NOT NULL REFERENCES booths(booth_id),
    menu_id TEXT NOT NULL REFERENCES menus(menu_id),
    sales_quantity INTEGER NOT NULL,
    revenue INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS weather (
    timestamp TEXT PRIMARY KEY,
    temperature REAL NOT NULL,
    precipitation_probability REAL NOT NULL,
    rainfall REAL NOT NULL,
    humidity REAL NOT NULL,
    provider TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS festival_events (
    event_id TEXT PRIMARY KEY,
    event_name TEXT NOT NULL,
    zone TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    expected_crowd INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    booth_id TEXT NOT NULL REFERENCES booths(booth_id),
    menu_id TEXT NOT NULL REFERENCES menus(menu_id),
    predicted_sales_30m INTEGER NOT NULL,
    predicted_sales_60m INTEGER NOT NULL,
    predicted_sales_until_close INTEGER NOT NULL,
    expected_remaining INTEGER NOT NULL,
    estimated_stockout_at TEXT,
    minutes_to_stockout INTEGER,
    stockout_before_close INTEGER NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL,
    model_source TEXT NOT NULL,
    drivers_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_actions (
    action_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    booth_id TEXT NOT NULL REFERENCES booths(booth_id),
    action_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    approved_at TEXT,
    executed_at TEXT
);
CREATE TABLE IF NOT EXISTS promotions (
    promotion_id TEXT PRIMARY KEY,
    booth_id TEXT NOT NULL REFERENCES booths(booth_id),
    discount_rate INTEGER NOT NULL,
    title TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS data_sources (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    period TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    data_class TEXT NOT NULL,
    last_validated_at TEXT
);
CREATE TABLE IF NOT EXISTS ml_runs (
    run_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    model_name TEXT NOT NULL,
    training_years TEXT NOT NULL,
    train_rows INTEGER NOT NULL,
    validation_year INTEGER NOT NULL,
    mae REAL NOT NULL,
    r2 REAL NOT NULL,
    status TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    stages_json TEXT NOT NULL
);
"""


@contextmanager
def connection(db_path: Path | str = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def initialize_database(db_path: Path | str = DB_PATH) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    historical_rows = len(_read_csv("sample_historical_sales.csv"))
    with connection(path) as conn:
        conn.executescript(SCHEMA)
        existing_prediction_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(predictions)").fetchall()
        }
        for definition in [
            "estimated_stockout_at TEXT",
            "minutes_to_stockout INTEGER",
            "stockout_before_close INTEGER NOT NULL DEFAULT 0",
        ]:
            column_name = definition.split()[0]
            if column_name not in existing_prediction_columns:
                conn.execute(f"ALTER TABLE predictions ADD COLUMN {definition}")
        conn.execute(
            """INSERT OR IGNORE INTO data_sources
               (source_id, source_name, source_type, period, row_count, status, data_class, last_validated_at)
               VALUES ('history-sample', 'Cross-campus Festival History', 'CSV', '2023–2025', ?,
                       'READY', 'SAMPLE / SYNTHETIC', ?)""",
            (historical_rows, DEMO_TIME),
        )
        exists = conn.execute("SELECT 1 FROM universities LIMIT 1").fetchone()
    if not exists:
        seed_demo_data(path)


def reset_demo(db_path: Path | str = DB_PATH) -> None:
    path = Path(db_path)
    if path.exists():
        path.unlink()
    initialize_database(path)


def seed_demo_data(db_path: Path | str = DB_PATH) -> None:
    with connection(db_path) as conn:
        conn.execute(
            "INSERT INTO universities VALUES (?, ?, ?, ?)",
            ("univ-zero", "제로대학교", "서울", 15000),
        )
        conn.execute(
            "INSERT INTO festivals VALUES (?, ?, ?, ?, ?, ?)",
            ("festival-2026", "univ-zero", "2026 Zero Festival", "2026-05-22", "16:00", "22:00"),
        )
        booths = [
            ("booth-chicken", "festival-2026", "청춘 닭꼬치", "A", 37.001, 127.001),
            ("booth-drink", "festival-2026", "파도 음료", "B", 37.002, 127.003),
            ("booth-tteok", "festival-2026", "응원단 떡볶이", "C", 37.000, 127.004),
            ("booth-waffle", "festival-2026", "와플 연구소", "B", 37.003, 127.002),
        ]
        conn.executemany("INSERT INTO booths VALUES (?, ?, ?, ?, ?, ?)", booths)
        menus = [
            ("menu-chicken", "booth-chicken", "닭꼬치", "food", 6000, 300),
            ("menu-drink", "booth-drink", "레몬 에이드", "drink", 3000, 157),
            ("menu-tteok", "booth-tteok", "떡볶이", "food", 5000, 161),
            ("menu-waffle", "booth-waffle", "초코 와플", "dessert", 4000, 108),
        ]
        conn.executemany("INSERT INTO menus VALUES (?, ?, ?, ?, ?, ?)", menus)

        for row in _read_csv("sample_inventory.csv"):
            conn.execute(
                """INSERT INTO inventory_snapshots
                   (timestamp, booth_id, menu_id, current_stock, additional_stock)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    row["timestamp"], row["booth_id"], row["menu_id"],
                    int(row["current_stock"]), int(row["additional_stock"]),
                ),
            )
        for row in _read_csv("sample_sales.csv"):
            conn.execute(
                """INSERT INTO sales_snapshots
                   (timestamp, booth_id, menu_id, sales_quantity, revenue)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    row["timestamp"], row["booth_id"], row["menu_id"],
                    int(row["sales_quantity"]), int(row["revenue"]),
                ),
            )
        for row in _read_csv("sample_weather.csv"):
            conn.execute(
                "INSERT INTO weather VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["timestamp"], float(row["temperature"]),
                    float(row["precipitation_probability"]), float(row["rainfall"]),
                    float(row["humidity"]), row["provider"],
                ),
            )
        for row in _read_csv("sample_events.csv"):
            conn.execute(
                "INSERT INTO festival_events VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["event_id"], row["event_name"], row["zone"],
                    row["start_time"], row["end_time"], int(row["expected_crowd"]),
                ),
            )
        settings = {
            "demo_time": DEMO_TIME,
            "demo_mode": "1",
            "student_response_simulated": "0",
            "festival_total_days": "3",
            "data_disclaimer": "Sample / Synthetic Festival Dataset",
        }
        conn.executemany("INSERT INTO settings VALUES (?, ?)", settings.items())


def query_all(sql: str, params: tuple[Any, ...] = (), db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def query_one(sql: str, params: tuple[Any, ...] = (), db_path: Path | str = DB_PATH) -> dict[str, Any] | None:
    rows = query_all(sql, params, db_path)
    return rows[0] if rows else None


def get_setting(key: str, default: str = "", db_path: Path | str = DB_PATH) -> str:
    row = query_one("SELECT value FROM settings WHERE key = ?", (key,), db_path)
    return str(row["value"]) if row else default


def set_setting(key: str, value: str, db_path: Path | str = DB_PATH) -> None:
    with connection(db_path) as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_demo_time(db_path: Path | str = DB_PATH) -> datetime:
    return datetime.fromisoformat(get_setting("demo_time", DEMO_TIME, db_path))


def get_booths(db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    return query_all(
        """SELECT b.booth_id, b.booth_name, b.zone, m.menu_id, m.menu_name,
                  m.category, m.price, m.initial_stock
           FROM booths b JOIN menus m ON m.booth_id = b.booth_id
           ORDER BY b.zone, b.booth_name""",
        db_path=db_path,
    )


def register_booth(
    booth_name: str,
    zone: str,
    menu_name: str,
    price: int,
    initial_stock: int,
    category: str = "food",
    db_path: Path | str = DB_PATH,
) -> str:
    """Register the P0 minimum booth/menu/inventory fields."""
    if not booth_name.strip() or not menu_name.strip():
        raise ValueError("부스명과 메뉴명은 필수입니다.")
    if price <= 0 or initial_stock < 0:
        raise ValueError("가격은 0보다 커야 하고 재고는 음수가 될 수 없습니다.")
    suffix = uuid.uuid4().hex[:8]
    booth_id, menu_id = f"booth-{suffix}", f"menu-{suffix}"
    now = get_demo_time(db_path).isoformat()
    zone_index = {"A": 1, "B": 2, "C": 3}.get(zone, 0)
    with connection(db_path) as conn:
        conn.execute(
            "INSERT INTO booths VALUES (?, 'festival-2026', ?, ?, ?, ?)",
            (booth_id, booth_name.strip(), zone, 37.0 + zone_index / 1000, 127.0 + zone_index / 1000),
        )
        conn.execute(
            "INSERT INTO menus VALUES (?, ?, ?, ?, ?, ?)",
            (menu_id, booth_id, menu_name.strip(), category, int(price), int(initial_stock)),
        )
        conn.execute(
            """INSERT INTO inventory_snapshots
               (timestamp, booth_id, menu_id, current_stock, additional_stock)
               VALUES (?, ?, ?, ?, 0)""",
            (now, booth_id, menu_id, int(initial_stock)),
        )
    return booth_id


def get_booth_state(booth_id: str, db_path: Path | str = DB_PATH) -> dict[str, Any]:
    row = query_one(
        """SELECT b.booth_id, b.booth_name, b.zone, m.menu_id, m.menu_name,
                  m.category, m.price, m.initial_stock,
                  f.date AS festival_date, f.start_time AS festival_start_time, f.end_time AS festival_end_time,
                  u.student_count,
                  i.current_stock, i.additional_stock,
                  COALESCE((SELECT SUM(s.sales_quantity) FROM sales_snapshots s
                            WHERE s.booth_id=b.booth_id), 0) AS total_sales,
                  COALESCE((SELECT SUM(s.revenue) FROM sales_snapshots s
                            WHERE s.booth_id=b.booth_id), 0) AS total_revenue
           FROM booths b
           JOIN festivals f ON f.festival_id=b.festival_id
           JOIN universities u ON u.university_id=f.university_id
           JOIN menus m ON m.booth_id=b.booth_id
           JOIN inventory_snapshots i ON i.snapshot_id=(
               SELECT snapshot_id FROM inventory_snapshots
               WHERE booth_id=b.booth_id ORDER BY timestamp DESC, snapshot_id DESC LIMIT 1
           )
           WHERE b.booth_id=?""",
        (booth_id,),
        db_path,
    )
    if not row:
        raise ValueError(f"Unknown booth: {booth_id}")
    recent = query_all(
        """SELECT sales_quantity FROM sales_snapshots WHERE booth_id=?
           ORDER BY timestamp DESC, snapshot_id DESC LIMIT 2""",
        (booth_id,),
        db_path,
    )
    row["recent_sales_30m"] = int(recent[0]["sales_quantity"]) if recent else 0
    row["previous_sales_30m"] = int(recent[1]["sales_quantity"]) if len(recent) > 1 else row["recent_sales_30m"]
    row["student_response_simulated"] = get_setting("student_response_simulated", "0", db_path) == "1"
    row["festival_total_days"] = int(get_setting("festival_total_days", "3", db_path))
    promo = query_one(
        "SELECT * FROM promotions WHERE booth_id=? AND status='ACTIVE' ORDER BY start_time DESC LIMIT 1",
        (booth_id,), db_path,
    )
    row["active_discount_rate"] = int(promo["discount_rate"]) if promo else 0
    return row


def get_weather_context(db_path: Path | str = DB_PATH) -> dict[str, Any]:
    now = get_demo_time(db_path).isoformat()
    current = query_one("SELECT * FROM weather WHERE timestamp<=? ORDER BY timestamp DESC LIMIT 1", (now,), db_path)
    future = query_one("SELECT * FROM weather WHERE timestamp>? ORDER BY timestamp ASC LIMIT 1", (now,), db_path)
    return {"current": current or {}, "forecast_1h": future or current or {}}


def get_event_context(db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    now = get_demo_time(db_path).isoformat()
    return query_all(
        "SELECT * FROM festival_events WHERE end_time>=? ORDER BY start_time", (now,), db_path
    )


def get_latest_prediction(booth_id: str, db_path: Path | str = DB_PATH) -> dict[str, Any] | None:
    row = query_one(
        "SELECT * FROM predictions WHERE booth_id=? ORDER BY prediction_id DESC LIMIT 1",
        (booth_id,), db_path,
    )
    if row:
        row["drivers"] = json.loads(row.pop("drivers_json", "[]"))
    return row


def save_prediction(booth_id: str, prediction: dict[str, Any], db_path: Path | str = DB_PATH) -> None:
    state = get_booth_state(booth_id, db_path)
    with connection(db_path) as conn:
        conn.execute(
            """INSERT INTO predictions
               (timestamp, booth_id, menu_id, predicted_sales_30m, predicted_sales_60m,
                predicted_sales_until_close, expected_remaining, estimated_stockout_at,
                minutes_to_stockout, stockout_before_close, risk_level, model_source, drivers_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                get_demo_time(db_path).isoformat(), booth_id, state["menu_id"],
                prediction["predicted_sales_30m"], prediction["predicted_sales_60m"],
                prediction["predicted_sales_until_close"], prediction["expected_remaining"],
                prediction.get("estimated_stockout_at"), prediction.get("minutes_to_stockout"),
                int(bool(prediction.get("stockout_before_close"))),
                prediction["risk_level"], prediction["model_source"],
                json.dumps(prediction.get("drivers", []), ensure_ascii=False),
            ),
        )


def replace_pending_actions(booth_id: str, candidates: list[dict[str, str]], db_path: Path | str = DB_PATH) -> None:
    now = get_demo_time(db_path).isoformat()
    with connection(db_path) as conn:
        conn.execute("DELETE FROM agent_actions WHERE booth_id=? AND status='PENDING'", (booth_id,))
        conn.executemany(
            """INSERT INTO agent_actions(action_id, timestamp, booth_id, action_type, reason, status)
               VALUES (?, ?, ?, ?, ?, 'PENDING')""",
            [(str(uuid.uuid4()), now, booth_id, item["action_type"], item["reason"]) for item in candidates],
        )


def get_actions(booth_id: str, status: str | None = None, db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    if status:
        return query_all(
            "SELECT * FROM agent_actions WHERE booth_id=? AND status=? ORDER BY timestamp DESC",
            (booth_id, status), db_path,
        )
    return query_all(
        "SELECT * FROM agent_actions WHERE booth_id=? ORDER BY timestamp DESC", (booth_id,), db_path
    )


def mark_action(action_id: str, status: str, db_path: Path | str = DB_PATH) -> None:
    now = get_demo_time(db_path).isoformat()
    field = "approved_at" if status == "APPROVED" else "executed_at"
    with connection(db_path) as conn:
        conn.execute(
            f"UPDATE agent_actions SET status=?, {field}=? WHERE action_id=?",
            (status, now, action_id),
        )


def get_action(action_id: str, db_path: Path | str = DB_PATH) -> dict[str, Any] | None:
    return query_one("SELECT * FROM agent_actions WHERE action_id=?", (action_id,), db_path)


def activate_promotion(booth_id: str, discount_rate: int = 20, db_path: Path | str = DB_PATH) -> None:
    now = get_demo_time(db_path)
    booth = get_booth_state(booth_id, db_path)
    with connection(db_path) as conn:
        conn.execute("UPDATE promotions SET status='ENDED' WHERE booth_id=? AND status='ACTIVE'", (booth_id,))
        conn.execute(
            "INSERT INTO promotions VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')",
            (
                str(uuid.uuid4()), booth_id, discount_rate,
                f"🔥 {booth['menu_name']} 마감 할인",
                now.isoformat(), (now + timedelta(hours=1)).isoformat(),
            ),
        )


def get_active_promotions(db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    return query_all(
        """SELECT p.*, b.booth_name, b.zone, m.menu_name, m.price,
                  CAST(ROUND(m.price * (100-p.discount_rate) / 100.0, -2) AS INTEGER) AS sale_price
           FROM promotions p JOIN booths b ON b.booth_id=p.booth_id
           JOIN menus m ON m.booth_id=b.booth_id
           WHERE p.status='ACTIVE' ORDER BY p.discount_rate DESC""",
        db_path=db_path,
    )


def record_sale(booth_id: str, quantity: int, db_path: Path | str = DB_PATH) -> None:
    if quantity <= 0:
        return
    state = get_booth_state(booth_id, db_path)
    sold = min(quantity, int(state["current_stock"]))
    unit_price = int(round(int(state["price"]) * (100 - int(state.get("active_discount_rate", 0))) / 100))
    timestamp = get_demo_time(db_path).isoformat()
    with connection(db_path) as conn:
        conn.execute(
            """INSERT INTO sales_snapshots(timestamp, booth_id, menu_id, sales_quantity, revenue)
               VALUES (?, ?, ?, ?, ?)""",
            (timestamp, booth_id, state["menu_id"], sold, sold * unit_price),
        )
        conn.execute(
            """INSERT INTO inventory_snapshots(timestamp, booth_id, menu_id, current_stock, additional_stock)
               VALUES (?, ?, ?, ?, 0)""",
            (timestamp, booth_id, state["menu_id"], max(0, int(state["current_stock"]) - sold)),
        )


def adjust_stock(booth_id: str, delta: int, db_path: Path | str = DB_PATH) -> None:
    state = get_booth_state(booth_id, db_path)
    new_stock = max(0, int(state["current_stock"]) + delta)
    with connection(db_path) as conn:
        conn.execute(
            """INSERT INTO inventory_snapshots(timestamp, booth_id, menu_id, current_stock, additional_stock)
               VALUES (?, ?, ?, ?, ?)""",
            (get_demo_time(db_path).isoformat(), booth_id, state["menu_id"], new_stock, max(delta, 0)),
        )


def simulate_student_response(db_path: Path | str = DB_PATH) -> None:
    set_setting("student_response_simulated", "1", db_path)


def dashboard_rows(db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for booth in get_booths(db_path):
        state = get_booth_state(booth["booth_id"], db_path)
        prediction = get_latest_prediction(booth["booth_id"], db_path) or {}
        action = query_one(
            """SELECT action_type, status FROM agent_actions WHERE booth_id=?
               ORDER BY CASE status WHEN 'PENDING' THEN 0 WHEN 'EXECUTED' THEN 1 ELSE 2 END, timestamp DESC LIMIT 1""",
            (booth["booth_id"],), db_path,
        ) or {}
        rows.append({**state, **prediction, "action_type": action.get("action_type", "-")})
    return rows

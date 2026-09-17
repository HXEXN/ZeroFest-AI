"""Regression tests for SQLite live synchronization."""

from __future__ import annotations

from services import database as db


def test_sqlite_sync_uses_wal_and_revision(tmp_path):
    path = tmp_path / "sync-test.db"
    db.initialize_database(path)

    status = db.sqlite_sync_status(path)
    assert str(status["journal_mode"]).lower() == "wal"

    before = db.get_runtime_revision(path)
    state_before = db.get_booth_state("booth-chicken", path)

    db.record_sale("booth-chicken", 1, db_path=path)

    after = db.get_runtime_revision(path)
    state_after = db.get_booth_state("booth-chicken", path)

    assert after > before
    assert state_after["total_sales"] == state_before["total_sales"] + 1
    assert state_after["current_stock"] == state_before["current_stock"] - 1


def test_reset_is_transactional_and_keeps_db_file(tmp_path):
    path = tmp_path / "sync-reset.db"
    db.initialize_database(path)

    db.record_sale("booth-chicken", 5, db_path=path)
    inode_before = path.stat().st_ino

    db.reset_demo(path)

    inode_after = path.stat().st_ino
    state = db.get_booth_state("booth-chicken", path)

    assert inode_after == inode_before
    assert db.get_setting("active_booth_id", "", path) == "booth-chicken"
    assert db.get_runtime_revision(path) >= 1
    assert state["current_stock"] >= 0


def test_pos_sync_event_is_visible_from_fresh_connection(tmp_path):
    path = tmp_path / "sync-event.db"
    db.initialize_database(path)

    before = db.get_booth_state("booth-chicken", path)
    db.record_sale("booth-chicken", 10, db_path=path)

    event = db.publish_pos_sync_event(
        "sale",
        "booth-chicken",
        quantity=10,
        db_path=path,
    )

    # verify_pos_sim_sync opens new connections internally,
    # mirroring a separate Streamlit page/session.
    check = db.verify_pos_sim_sync("booth-chicken", path)
    after = db.get_booth_state("booth-chicken", path)

    assert event["event_id"]
    assert check["wal_ok"] is True
    assert check["event_seen"] is True
    assert check["same_booth"] is True
    assert check["revision_ok"] is True
    assert check["state_ok"] is True
    assert after["total_sales"] == before["total_sales"] + 10
    assert after["current_stock"] == before["current_stock"] - 10

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

"""Data and integration services.

The database module is patched at package import time so every Streamlit page
uses the same WAL-enabled, transaction-safe SQLite behavior.
"""

from . import database as database
from .sqlite_sync import install_sqlite_sync

install_sqlite_sync(database)

__all__ = ["database"]

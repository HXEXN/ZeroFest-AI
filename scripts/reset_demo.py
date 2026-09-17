#!/usr/bin/env python3
"""Reset SQLite and materialize fresh baseline predictions."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.graph import analyze_all  # noqa: E402
from services.database import reset_demo  # noqa: E402


if __name__ == "__main__":
    reset_demo()
    results = analyze_all()
    print(f"Demo reset complete: {len(results)} booths analyzed")


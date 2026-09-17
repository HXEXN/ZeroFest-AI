"""Application-wide configuration for the offline-first ZeroFest demo."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "zerofest.db"
DEMO_TIME = "2026-05-22T19:00:00"

load_dotenv(ROOT_DIR / ".env")

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}
RISK_LOW_THRESHOLD = float(os.getenv("RISK_LOW_THRESHOLD", "0.10"))
RISK_HIGH_THRESHOLD = float(os.getenv("RISK_HIGH_THRESHOLD", "0.30"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_historical_path = os.getenv("HISTORICAL_DATA_PATH", "").strip()
HISTORICAL_DATA_PATH = Path(_historical_path) if _historical_path else DATA_DIR / "sample_historical_sales.csv"


ACTION_LABELS = {
    "MAINTAIN": "현재 운영 유지",
    "STOP_COOKING": "추가 조리 중단",
    "DISCOUNT": "20% 마감 할인",
    "TRANSFER": "B구역으로 재고 이동",
    "PROMOTION": "학생 프로모션 활성화",
    "DONATE": "나눔 연계 검토",
    "MONITOR": "15분 후 재확인",
}

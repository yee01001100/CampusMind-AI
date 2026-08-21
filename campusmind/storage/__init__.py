"""SQLite storage primitives and deterministic demo-data loading."""

from .database import SQLiteDatabase
from .demo import DemoLoadResult, load_demo_data

__all__ = ["DemoLoadResult", "SQLiteDatabase", "load_demo_data"]

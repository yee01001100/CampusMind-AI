"""Command-line initializer for a local, ignored demo database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from campusmind.repositories import KnowledgeImporter

from .database import SQLiteDatabase
from .demo import load_demo_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize CampusMind simulated data")
    parser.add_argument(
        "--database", default="data/local/campusmind-demo.sqlite3",
        help="SQLite output path (runtime databases are gitignored)",
    )
    parser.add_argument("--demo-dir", default="data/demo")
    parser.add_argument("--knowledge-dir", default="data/knowledge")
    parser.add_argument("--without-knowledge", action="store_true")
    args = parser.parse_args()

    database = SQLiteDatabase(Path(args.database))
    demo = load_demo_data(database, Path(args.demo_dir))
    result: dict[str, object] = {"database": args.database, "demo": demo.__dict__}
    if not args.without_knowledge:
        result["knowledge"] = KnowledgeImporter(database).import_directory(
            Path(args.knowledge_dir)
        ).__dict__
    # ASCII JSON prints reliably even in legacy Windows terminal encodings.
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

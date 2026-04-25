"""Small sqlite3 CLI fallback for environments without the sqlite3 binary."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def run_sql(db_path: Path, sql: str) -> int:
    if sql == ".tables":
        sql = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.executescript(sql) if ";" in sql.strip()[:-1] else conn.execute(sql)
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            print("\t".join(columns))
            for row in cursor.fetchall():
                print("\t".join("" if row[col] is None else str(row[col]) for col in columns))
    return 0


def interactive(db_path: Path) -> int:
    print(f"Connected to {db_path}. Use .quit to exit.")
    while True:
        try:
            sql = input("sqlite> ").strip()
        except EOFError:
            print()
            return 0
        if not sql:
            continue
        if sql in {".quit", ".exit"}:
            return 0
        if sql == ".tables":
            sql = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        try:
            run_sql(db_path, sql)
        except sqlite3.Error as exc:
            print(f"error: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Project-local sqlite3 fallback.")
    parser.add_argument("database", type=Path)
    parser.add_argument("sql", nargs="?", help="SQL to execute. Omit for interactive mode.")
    args = parser.parse_args()

    args.database.parent.mkdir(parents=True, exist_ok=True)
    if args.sql:
        return run_sql(args.database, args.sql)
    return interactive(args.database)


if __name__ == "__main__":
    raise SystemExit(main())

"""Run a docs/ux-evidence SQL file in a read-only session; prints plain-text tables.

Usage: backend/.venv/Scripts/python.exe docs/ux-evidence/run_sql.py <file.sql>
Reads DATABASE_URL from the repo's .env and never prints it.
"""

import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]


def database_url() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').replace("+psycopg", "")
    raise SystemExit("DATABASE_URL not found in .env")


def main(path: str) -> None:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    body = [ln for ln in lines if not ln.startswith("--")]
    # \echo lines become section titles; each section ends with one statement.
    with psycopg.connect(database_url(), connect_timeout=10, autocommit=True) as conn:
        conn.execute("SET default_transaction_read_only = on")
        buffer: list[str] = []
        for line in body:
            if line.startswith("\\echo"):
                print("\n" + line.split(" ", 1)[1].strip("'"))
                continue
            buffer.append(line)
            if line.rstrip().endswith(";"):
                statement = "\n".join(buffer).strip()
                buffer = []
                if statement.upper().startswith(("BEGIN", "ROLLBACK")):
                    continue
                cur = conn.execute(statement)
                print(" | ".join(col.name for col in cur.description))
                for row in cur.fetchall():
                    print(" | ".join(str(value) for value in row))


if __name__ == "__main__":
    main(sys.argv[1])

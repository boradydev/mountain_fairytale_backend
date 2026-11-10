"""Provision UUID-owned test databases; preserve protected databases and evidence."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql


def connect(name, **kwargs):
    return psycopg.connect(host="127.0.0.1", port=5432, user="postgres", password="postgres", dbname=name, **kwargs)


def fingerprint(name):
    with connect(name) as db:
        result = {}
        for (table,) in db.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ).fetchall():
            rows = db.execute(
                sql.SQL("SELECT row_to_json(t)::text FROM {} t ORDER BY 1").format(sql.Identifier(table))
            ).fetchall()
            result[table] = {
                "count": len(rows),
                "sha256": hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest(),
            }
        return result


def main():
    run_id = uuid4().hex
    evidence = Path(".codex-tmp") / ("resilience-" + run_id)
    evidence.mkdir(parents=True)
    protected = ["mountain_fairytale_qa", "mountain_fairytale_load"]
    before = {name: fingerprint(name) for name in protected}
    (evidence / "protected-before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    owned = []
    env = {
        **os.environ,
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
        "RESILIENCE_TCP": "1",
        "TEMP": str(Path(".codex-tmp").resolve()),
        "TMP": str(Path(".codex-tmp").resolve()),
    }
    try:
        with connect("postgres", autocommit=True) as admin:
            for kind, variable in (("api", "POSTGRES_API_TEST_DB"), ("repo", "POSTGRES_REPO_TEST_DB")):
                name = f"mf_resilience_{kind}_{run_id}_test"
                assert len(name) < 64
                assert name.endswith(run_id + "_test")
                assert admin.execute("SELECT oid FROM pg_database WHERE datname=%s", (name,)).fetchone() is None
                admin.execute(
                    sql.SQL(
                        "CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8' "
                        "LC_COLLATE 'Russian_Russia.utf8' LC_CTYPE 'Russian_Russia.utf8'"
                    ).format(sql.Identifier(name))
                )
                oid = admin.execute("SELECT oid FROM pg_database WHERE datname=%s", (name,)).fetchone()[0]
                owned.append((name, oid))
                env[variable] = name
                with connect(name) as db:
                    assert db.execute("SELECT current_database()").fetchone()[0] == name
        (evidence / "ownership.json").write_text(json.dumps(owned), encoding="utf-8")
        print(f"Evidence: {evidence}", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *sys.argv[1:], "--basetemp=.codex-tmp/pytest"], env=env, check=False
        )
        return result.returncode
    finally:
        after = {name: fingerprint(name) for name in protected}
        (evidence / "protected-after.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
        assert before == after, "Protected QA/LOAD changed"
        with connect("postgres", autocommit=True) as admin:
            for name, oid in owned:
                assert name.endswith(run_id + "_test")
                assert admin.execute("SELECT oid FROM pg_database WHERE datname=%s", (name,)).fetchone() == (oid,)
                assert admin.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=%s", (name,)).fetchone() == (
                    0,
                )
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
        print("Protected QA/LOAD unchanged; owned databases removed.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())

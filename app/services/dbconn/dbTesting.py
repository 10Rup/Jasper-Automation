import time
from contextlib import contextmanager

CONNECT_TIMEOUT = 5  # seconds — never let a test hang the request thread



@contextmanager
def maybe_ssh_tunnel(c: dict):
    if not c.get("ssl"):
        yield c["host"], c["port"]
        return

    from sshtunnel import SSHTunnelForwarder

    tunnel_kwargs = dict(
        ssh_address_or_host=(c["sshHost"], int(c.get("sshPort") or 22)),
        ssh_username=c["sshUser"],
        remote_bind_address=(c["host"], int(c["port"])),
    )

    if c.get("authMode") == "key":
        tunnel_kwargs["ssh_pkey"] = c["ssh_key_path"]     # see note below re: .ppk
        if c.get("keyPass"):
            tunnel_kwargs["ssh_private_key_password"] = c["keyPass"]
    else:
        tunnel_kwargs["ssh_password"] = c["sshPass"]

    with SSHTunnelForwarder(**tunnel_kwargs) as tunnel:
        yield "127.0.0.1", tunnel.local_bind_port


def test_connection(c: dict) -> dict:
    """c is a plain dict: {type, host, port, db, user, pass, ssl, sshHost, ...}"""
    start = time.perf_counter()
    
    try:
        with maybe_ssh_tunnel(c) as (host, port):
            tester = TESTERS.get(c["type"])
            if not tester:
                return {"ok": False, "error": f"unsupported engine: {c['type']}"}
            tester(c, host, port)
        latency_ms = round((time.perf_counter() - start) * 1000)
        return {"ok": True, "latency_ms": latency_ms}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _test_postgres(c, host, port):
    import psycopg2
    conn = psycopg2.connect(
        host=host, port=port, dbname=c.get("db") or "postgres",
        user=c["user"], password=c["dbpass"], connect_timeout=CONNECT_TIMEOUT,
    )
    conn.close()

def _test_mysql(c, host, port):
    import pymysql
    conn = pymysql.connect(
        host=host, port=int(port), db=c.get("db") or None,
        user=c["user"], password=c["dbpass"], connect_timeout=CONNECT_TIMEOUT,
    )
    conn.close()

def _test_mssql(c, host, port):
    import pyodbc
    conn = pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={host},{port};"
        f"DATABASE={c.get('db') or 'master'};UID={c['user']};PWD={c['dbpass']};"
        f"Encrypt=yes;TrustServerCertificate=yes;Connection Timeout={CONNECT_TIMEOUT}",
    )
    conn.close()

def _test_mongo(c, host, port):
    from pymongo import MongoClient
    client = MongoClient(
        host=host, port=int(port), username=c.get("user") or None,
        password=c.get("dbpass") or None, serverSelectionTimeoutMS=CONNECT_TIMEOUT * 1000,
    )
    client.admin.command("ping")  # forces an actual round trip
    client.close()

def _test_redis(c, host, port):
    import redis
    r = redis.Redis(host=host, port=int(port), password=c.get("dbpass") or None,
                     socket_connect_timeout=CONNECT_TIMEOUT)
    r.ping()

def _test_sqlite(c, host, port):
    import sqlite3, os
    path = c.get("db") or c.get("host")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no sqlite file at {path}")
    conn = sqlite3.connect(path, timeout=CONNECT_TIMEOUT)
    conn.execute("SELECT 1")
    conn.close()

TESTERS = {
    "postgres": _test_postgres,
    "mysql": _test_mysql,
    "sqlserver": _test_mssql,
    "mongodb": _test_mongo,
    "redis": _test_redis,
    "sqlite": _test_sqlite,
    # add oracle / clickhouse the same way when you need them
}
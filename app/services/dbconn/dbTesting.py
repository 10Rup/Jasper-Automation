import os
import time
import uuid
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote_plus
from decimal import Decimal
from datetime import date, datetime

from sqlalchemy import create_engine, inspect, MetaData, Table, select, func, text
from sqlalchemy.orm import Session

from ...models.model import SshKey
import paramiko

CONNECT_TIMEOUT = 5  # seconds — never let a test hang the request thread
SSH_KEY_DIR = Path(os.getenv("SSH_KEY_DIR", "storage/ssh_keys"))
SSH_KEY_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------------------

def looks_like_pem(file_bytes: bytes) -> bool:
    return file_bytes.lstrip()[:40].startswith(b"-----BEGIN")

def save_ssh_key(name: str, filename: str, file_bytes: bytes, db: Session) -> SshKey:
    """Saves a standalone .pem key — independent of any connection, selected later by ID."""
    if not looks_like_pem(file_bytes):
        raise ValueError("that file doesn't look like a valid .pem private key")

    safe_name = os.path.basename(filename or "key.pem")
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    key_path = SSH_KEY_DIR / stored_name

    with open(key_path, "wb") as f:
        f.write(file_bytes)
    os.chmod(key_path, 0o600)

    row = SshKey(
        name=name.strip() or safe_name,
        original_filename=safe_name,
        stored_filename=stored_name,
        storage_path=str(key_path),
    )
    db.add(row)
    db.flush()
    return row

# -------------------------------------------------------------------------------------------------

# def looks_like_pem(file_bytes: bytes) -> bool:
#     """
#     Quick sanity check so a wrong/corrupted upload fails with a clear message
#     here, instead of a confusing error deep inside paramiko later.
#     """
#     head = file_bytes.lstrip()[:40]
#     return head.startswith(b"-----BEGIN")

def load_private_key(path: str, passphrase: str | None = None):
    """
    Loads a PEM private key directly via paramiko, instead of handing sshtunnel
    a file path — sshtunnel's own auto-detection loop still references
    paramiko.DSSKey internally, which was removed in paramiko 3.0+, so it
    crashes before even trying the actual key type. Loading explicitly here
    avoids that broken code path entirely.
    """
    key_classes = [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]
    errors = {}
    for key_class in key_classes:
        try:
            return key_class.from_private_key_file(path, password=passphrase or None)
        except paramiko.PasswordRequiredException:
            raise ValueError("this key is passphrase-protected — enter the passphrase and try again")
        except paramiko.SSHException as e:
            errors[key_class.__name__] = str(e)
            continue

    detail = "; ".join(f"{k}: {v}" for k, v in errors.items())
    raise ValueError(f"couldn't load '{path}' as RSA, Ed25519, or ECDSA — {detail}")


def write_temp_ssh_key(filename: str, file_bytes: bytes) -> dict:
    """
    Writes an uploaded .pem key to a temp file, for testing a connection that
    hasn't been saved yet (so there's no SshKey row to reuse).
    Returns:
      usable_path   - the path to hand to sshtunnel
      converted_ok  - False only if the file doesn't look like a PEM key at all
      cleanup_paths - the temp file(s) created, so the caller can remove them
    """
    if not looks_like_pem(file_bytes):
        # still write it so the caller can report a clean error without a stray temp file
        return {"usable_path": None, "converted_ok": False, "cleanup_paths": []}

    suffix = os.path.splitext(filename or "key.pem")[1] or ".pem"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(file_bytes)
    os.chmod(path, 0o600)

    return {"usable_path": path, "converted_ok": True, "cleanup_paths": [path]}


def save_key_file_to_disk(connection_id: int, filename: str, file_bytes: bytes, db: Session) -> SshKey:
    """
    Saves an uploaded .pem key to disk and records it in the ssh_keys table.
    One key per connection — re-uploading replaces the previous file and row.
    """
    conn_dir = SSH_KEY_DIR / str(connection_id)
    conn_dir.mkdir(parents=True, exist_ok=True)

    # never trust a client-supplied filename directly — strip any path components
    safe_name = os.path.basename(filename or "key.pem")
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    key_path = conn_dir / stored_name

    with open(key_path, "wb") as f:
        f.write(file_bytes)
    os.chmod(key_path, 0o600)  # private key — owner read/write only

    existing = db.query(SshKey).filter(SshKey.connection_id == connection_id).first()
    if existing:
        if existing.storage_path and os.path.exists(existing.storage_path):
            os.remove(existing.storage_path)
        existing.original_filename = safe_name
        existing.stored_filename = stored_name
        existing.storage_path = str(key_path)
        row = existing
    else:
        row = SshKey(
            connection_id=connection_id,
            original_filename=safe_name,
            stored_filename=stored_name,
            storage_path=str(key_path),
        )
        db.add(row)

    db.flush()  # row is queryable within this transaction without a full commit yet
    return row


# ============================================================
# Connection testing
# ============================================================

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
        key_path = c.get("ssh_key_path")
        if not key_path:
            raise ValueError("no SSH key is on file for this connection")
        tunnel_kwargs["ssh_pkey"] = load_private_key(key_path, c.get("keyPass"))
    else:
        tunnel_kwargs["ssh_password"] = c.get("sshPass")

    # if c.get("authMode") == "key":
    #     key_path = c.get("ssh_key_path")
    #     if not key_path:
    #         raise ValueError("no SSH key is on file for this connection")
    #     tunnel_kwargs["ssh_pkey"] = key_path
    #     if c.get("keyPass"):
    #         tunnel_kwargs["ssh_private_key_password"] = c["keyPass"]
    # else:
    #     tunnel_kwargs["ssh_password"] = c.get("sshPass")

    with SSHTunnelForwarder(**tunnel_kwargs) as tunnel:
        yield "127.0.0.1", tunnel.local_bind_port


def test_connection(c: dict) -> dict:
    """c is a plain dict: {type, host, port, db, user, dbpass, ssl, sshHost, ...}"""
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
    import sqlite3
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


# ============================================================
# Schema introspection
# ============================================================

def build_sqlalchemy_url(c: dict, host: str, port) -> str:
    user = quote_plus(c["user"] or "")
    pw = quote_plus(c["dbpass"] or "")
    db = c.get("db") or ""

    if c["type"] == "postgres":
        return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db or 'postgres'}"
    if c["type"] == "mysql":
        return f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}"
    if c["type"] == "sqlserver":
        return (f"mssql+pyodbc://{user}:{pw}@{host}:{port}/{db}"
                f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes")
    if c["type"] == "oracle":
        return f"oracle+cx_oracle://{user}:{pw}@{host}:{port}/?service_name={db}"
    if c["type"] == "sqlite":
        return f"sqlite:///{db or c['host']}"

    raise ValueError(f"{c['type']} isn't a SQLAlchemy-inspectable engine")

def _split_table_name(name: str, default_schema: str | None) -> tuple[str | None, str]:
    """'salesdb.students' -> ('salesdb', 'students'); 'students' -> (default_schema, 'students')"""
    if "." in name:
        schema, table = name.split(".", 1)
        return schema, table
    return default_schema, name


def list_tables(c: dict) -> list[str]:
    if c["type"] == "mongodb":
        from pymongo import MongoClient
        with maybe_ssh_tunnel(c) as (host, port):
            client = MongoClient(
                host=host, port=int(port), username=c.get("user") or None,
                password=c.get("dbpass") or None, serverSelectionTimeoutMS=CONNECT_TIMEOUT * 1000,
            )
            try:
                return sorted(client[c["db"]].list_collection_names())
            finally:
                client.close()

    if c["type"] == "redis":
        raise ValueError("Redis has no fixed schema — there's no table list to return")

    with maybe_ssh_tunnel(c) as (host, port):
        engine = create_engine(build_sqlalchemy_url(c, host, port),
                                connect_args={"connect_timeout": CONNECT_TIMEOUT})
        try:
            if c.get("db"):
                # a specific database is set on this connection — same behavior as before
                return sorted(inspect(engine).get_table_names())

            if c["type"] != "mysql":
                raise ValueError(
                    f"{c['type']} connections need a specific database selected — "
                    f"cross-database table listing is only supported for MySQL"
                )

            # no default database on this connection — list every table on the server,
            # qualified as "database.table" so the caller knows which schema each is in
            with engine.connect() as db_conn:
                result = db_conn.execute(text(
                    "SELECT table_schema, table_name FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys') "
                    "ORDER BY table_schema, table_name"
                ))
                return [f"{schema}.{table}" for schema, table in result.fetchall()]
        finally:
            engine.dispose()
# ============================================================
# Sample data
# ============================================================

def json_safe(value):
    if isinstance(value, Decimal): return float(value)
    if isinstance(value, (datetime, date)): return value.isoformat()
    if isinstance(value, (bytes, bytearray)): return value.decode(errors="replace")
    return value


def rows_to_dicts(rows, columns):
    return [{col: json_safe(v) for col, v in zip(columns, row)} for row in rows]

def get_sample_data(c: dict, table_names: list[str]) -> dict:
    with maybe_ssh_tunnel(c) as (host, port):
        engine = create_engine(build_sqlalchemy_url(c, host, port),
                                connect_args={"connect_timeout": CONNECT_TIMEOUT})
        try:
            insp = inspect(engine)
            default_schema = c.get("db") or None

            requested = [_split_table_name(t, default_schema) for t in table_names]
            resolved = []
            for schema, table in requested:
                try:
                    real_tables = set(insp.get_table_names(schema=schema))
                except Exception:
                    continue
                if table in real_tables:
                    resolved.append((schema, table))
            if not resolved:
                return {}

            selected = set(resolved)
            metadata = MetaData()

            def get_or_reflect(schema, table):
                """Reflects a table once and only once per MetaData, regardless of how
                many code paths ask for it — resolve_fks=False so SQLAlchemy never
                implicitly pulls in FK-referenced tables behind our back, which is what
                causes 'Table already defined' conflicts when multiple selected tables
                reference each other."""
                key = f"{schema}.{table}" if schema else table
                existing = metadata.tables.get(key)
                if existing is not None:
                    return existing
                return Table(table, metadata, schema=schema, autoload_with=engine, resolve_fks=False)

            # ---- 1. introspect PK + FKs per (schema, table) ----
            schema_info = {}
            for schema, table in resolved:
                pk_cols = insp.get_pk_constraint(table, schema=schema).get("constrained_columns") or []
                fks = insp.get_foreign_keys(table, schema=schema)
                schema_info[(schema, table)] = {"pk": pk_cols, "fks": fks}

            # ---- 2. classify children: FK into a selected table (possibly in another schema) ----
            child_links = {}
            for (schema, table), info in schema_info.items():
                for fk in info["fks"]:
                    parent_schema = fk.get("referred_schema") or schema
                    parent_key = (parent_schema, fk["referred_table"])
                    if parent_key not in selected or parent_key == (schema, table):
                        continue
                    fk_cols = fk["constrained_columns"]
                    if set(fk_cols) == set(info["pk"]):
                        continue
                    child_links[(schema, table)] = {
                        "parent": parent_key,
                        "fk_cols": fk_cols,
                        "parent_cols": fk["referred_columns"],
                    }
                    break

            # ---- 3. anchor: find a parent record with real repetition ----
            anchor = {}
            parents = {link["parent"] for link in child_links.values()}

            with engine.connect() as conn:
                for parent_key in parents:
                    child_key, link = next((k, l) for k, l in child_links.items() if l["parent"] == parent_key)
                    child_schema, child_table = child_key
                    child_tbl = get_or_reflect(child_schema, child_table)
                    fk_cols = [child_tbl.c[col] for col in link["fk_cols"]]

                    grouped = (
                        select(*fk_cols, func.count().label("n"))
                        .group_by(*fk_cols)
                        .having(func.count() >= 2)
                        .order_by(func.count().desc())
                        .limit(1)
                    )
                    row = conn.execute(grouped).first()
                    if row is None:
                        row = conn.execute(select(*fk_cols).limit(1)).first()
                    if row is not None:
                        values = row[:len(link["fk_cols"])]
                        anchor[parent_key] = dict(zip(link["parent_cols"], values))

            # ---- 4. pull the actual sample rows, keyed by "schema.table" ----
            samples = {}
            with engine.connect() as conn:
                for schema, table in resolved:
                    key = (schema, table)
                    tbl = get_or_reflect(schema, table)
                    columns = [col.name for col in tbl.columns]
                    output_key = f"{schema}.{table}" if schema else table

                    if key in child_links and child_links[key]["parent"] in anchor:
                        link = child_links[key]
                        parent_vals = anchor[link["parent"]]
                        where = [tbl.c[fk] == parent_vals[pk]
                                 for fk, pk in zip(link["fk_cols"], link["parent_cols"])]
                        q = select(tbl).where(*where).limit(4)
                    elif key in anchor:
                        where = [tbl.c[col] == val for col, val in anchor[key].items()]
                        q = select(tbl).where(*where).limit(1)
                    else:
                        q = select(tbl).limit(1)

                    result = conn.execute(q)
                    samples[output_key] = rows_to_dicts(result.fetchall(), columns)

            return samples
        finally:
            engine.dispose()

def get_sample_data_mongo(c: dict, table_names: list[str]) -> dict:
    from pymongo import MongoClient
    with maybe_ssh_tunnel(c) as (host, port):
        client = MongoClient(host=host, port=int(port), username=c.get("user") or None,
                              password=c.get("dbpass") or None,
                              serverSelectionTimeoutMS=CONNECT_TIMEOUT * 1000)
        try:
            db = client[c["db"]]
            samples = {}
            for coll_name in table_names:
                # cheap heuristic: if >1 doc shares the most common "*_id" field value, treat as repeater
                doc = db[coll_name].find_one()
                limit = 1
                if doc:
                    shared_key = next((k for k in doc if k.endswith("_id") and k != "_id"), None)
                    if shared_key:
                        dup = list(db[coll_name].aggregate([
                            {"$group": {"_id": f"${shared_key}", "n": {"$sum": 1}}},
                            {"$match": {"n": {"$gte": 2}}}, {"$limit": 1},
                        ]))
                        if dup:
                            limit = 4
                            samples[coll_name] = list(db[coll_name].find({shared_key: dup[0]["_id"]}).limit(4))
                            continue
                samples[coll_name] = list(db[coll_name].find().limit(limit))
            # Mongo ObjectId/datetime aren't JSON-serializable — convert
            import json
            from bson import json_util
            return json.loads(json_util.dumps(samples))
        finally:
            client.close()










def get_plain_sample_rows(c: dict, table_name: str, limit: int = 5) -> list[dict]:
    """
    Simple, unconditioned SELECT ... LIMIT N — no anchor/repeat logic (that's specific
    to get_sample_data's query-generation use case, where a coherent related record set
    matters more than raw row count). Used when we just want a representative slice of
    a table's actual data, e.g. for AI-generated table descriptions.
    """
    default_schema = c.get("db") or None
    schema, table = _split_table_name(table_name, default_schema)

    with maybe_ssh_tunnel(c) as (host, port):
        engine = create_engine(build_sqlalchemy_url(c, host, port),
                                connect_args={"connect_timeout": CONNECT_TIMEOUT})
        try:
            insp = inspect(engine)
            if table not in set(insp.get_table_names(schema=schema)):
                return []
            metadata = MetaData()
            tbl = Table(table, metadata, schema=schema, autoload_with=engine, resolve_fks=False)
            columns = [col.name for col in tbl.columns]
            with engine.connect() as db_conn:
                result = db_conn.execute(select(tbl).limit(limit))
                return rows_to_dicts(result.fetchall(), columns)
        finally:
            engine.dispose()


def get_plain_sample_rows_mongo(c: dict, table_name: str, limit: int = 5) -> list[dict]:
    from pymongo import MongoClient
    import json
    from bson import json_util

    with maybe_ssh_tunnel(c) as (host, port):
        client = MongoClient(host=host, port=int(port), username=c.get("user") or None,
                              password=c.get("dbpass") or None,
                              serverSelectionTimeoutMS=CONNECT_TIMEOUT * 1000)
        try:
            docs = list(client[c["db"]][table_name].find().limit(limit))
            return json.loads(json_util.dumps(docs))
        finally:
            client.close()
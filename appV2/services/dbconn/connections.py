from cryptography.fernet import Fernet, InvalidToken
import os



# Load once at import time — keep this key in an env var, never in source control.
# _FERNET = Fernet(os.environ["CREDENTIALS_ENCRYPTION_KEY"])


# def decrypt(value: str | None) -> str | None:
#     """Decrypts a value encrypted with encrypt(). Returns None if input is None/empty."""
#     if not value:
#         return None
#     try:
#         return _FERNET.decrypt(value.encode()).decode()
#     except InvalidToken as e:
#         # Don't leak ciphertext or key material into the error — just flag that
#         # this row's secret can't be read (bad key, corrupted value, etc.)
#         raise ValueError("stored credential could not be decrypted") from e


# def encrypt(value: str | None) -> str | None:
#     """Inverse of decrypt() — use this when saving a connection, not shown here since
#     that logic lives in your POST /db/add and PUT /db/{id} routes."""
#     if not value:
#         return None
#     return _FERNET.encrypt(value.encode()).decode()


# def build_conn_dict(connection) -> dict:
#     """
#     Converts a Dbcredentials SQLAlchemy row into the plain dict shape every
#     connection-using function expects (test_connection, list_tables, get_sample_data, ...).

#     Centralizing this means:
#       - decryption happens in exactly one place
#       - if a column gets renamed, only this function needs updating
#       - every route gets the same field set, so payloads sent to test_connection()
#         etc. are always shaped consistently
#     """
#     return {
#         "type": connection.type,
#         "host": connection.host,
#         "port": connection.port,
#         "db": connection.db,
#         "user": connection.user,
#         "dbpass": connection.dbpass,
#         "ssl": connection.ssl,
#         "sshHost": connection.sshHost,
#         "sshPort": connection.sshPort,
#         "sshUser": connection.sshUser,
#         "authMode": connection.authMode,
#         "sshPass": connection.sshPass,
#         "keyPass": connection.keyPass
#     }

def build_conn_dict(connection) -> dict:
    return {
        "type": connection.type,
        "host": connection.host,
        "port": connection.port,
        "db": connection.db,
        "user": connection.user,
        "dbpass": connection.dbpass,
        "ssl": connection.ssl,
        "sshHost": connection.sshHost,
        "sshPort": connection.sshPort,
        "sshUser": connection.sshUser,
        "authMode": connection.authMode,
        "sshPass": connection.sshPass,
        "keyPass": connection.keyPass,
        "ssh_key_path": connection.ssh_key.storage_path if connection.ssh_key else None,
    }
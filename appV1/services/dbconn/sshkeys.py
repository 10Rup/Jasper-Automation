import os
import uuid
from pathlib import Path
from sqlalchemy.orm import Session
from ...models.model import SshKey

SSH_KEY_DIR = Path(os.getenv("SSH_KEY_DIR", "storage/ssh_keys"))
SSH_KEY_DIR.mkdir(parents=True, exist_ok=True)


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
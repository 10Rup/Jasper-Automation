from sqlalchemy import func, JSON, Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship, backref
from datetime import datetime, timezone
from ..databases.db import Base

# Migration
# Since this is a new table, you'll need to create it — either via Alembic (alembic revision --autogenerate -m "add ssh_keys table" then alembic upgrade head) or, if you're not using migrations yet, Base.metadata.create_all(bind=engine) will pick it up on next app startup as long as this model is imported somewhere before that call runs.

class Upload(Base):
    __tablename__ = 'uploads'
    id = Column(Integer, primary_key=True, index=True)
    displayname = Column(String,index=True)
    name = Column(String,index=True)
    type = Column(String,index=True)
    path = Column(String, nullable=False)
    size = Column(String)
    pagedimention = Column(String)
    query = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)




class Process(Base):
    __tablename__ = 'processimages'
    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(Integer, ForeignKey('uploads.id'), nullable=False)
    bandname = Column(String, nullable=False)
    path = Column(String, default="")
    code = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)


    # 'type': 'mysql', 'name': 'localhost', 'host': 'localhost', 'port': '3306', 'db': '45435435', 'user': 'root', 'pass': '', 'ssl': False, 'sshHost': '', 'sshPort': '', 'sshUser': '', 'authMode': 'password', 'sshPass': '', 'keyPass': ''}


class Dbcredentials(Base):
    __tablename__ = 'dbcredentials'
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    host = Column(String, nullable=False)
    port = Column(String, nullable=False)
    db = Column(String, nullable=False)
    user = Column(String, nullable=False)
    dbpass = Column(String, nullable=False)
    status = Column(String, default="untested")

    ssl = Column(Boolean, default=False)
    sshHost = Column(String, nullable=True)
    sshPort = Column(Integer, nullable=True)
    sshUser = Column(String, nullable=True)
    authMode = Column(String, default="password")
    sshPass = Column(String, nullable=True)
    keyPass = Column(String, nullable=True)
    last_tested_at = Column(DateTime, nullable=True)
    ssh_key_id = Column(Integer, ForeignKey('ssh_keys.id'), nullable=True)
    ssh_key = relationship("SshKey")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

    @property
    def keyFileName(self):
        return self.ssh_key.original_filename if self.ssh_key else None


class SavedQuery(Base):
    __tablename__ = "saved_queries"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("dbcredentials.id"), nullable=False)
    dataset_name = Column(String(255), nullable=False)
    report_type = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tables = Column(JSON, nullable=False)        # ["students", "marks"]
    sample_json = Column(JSON, nullable=True)     # kept for reference/regeneration later
    sql_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    connection = relationship("Dbcredentials")


class SshKey(Base):
    __tablename__ = 'ssh_keys'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)                # user-given label shown in the dropdown, e.g. "Prod bastion"
    original_filename = Column(String, nullable=False)   # what was uploaded, e.g. "SMbastion.pem"
    stored_filename = Column(String, nullable=False)     # randomized name actually used on disk
    storage_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

'''
cmd:: 1. Disable permission inheritance on the file
icacls "C:\RUPMANDAL\TeamProject\Jasper-Automation\SMbastion.pem" /inheritance:r

:: 2. Grant full control ONLY to your currently logged-in user
icacls "C:\RUPMANDAL\TeamProject\Jasper-Automation\SMbastion.pem" /grant:r "%username%:F"

ssh-keygen -p -m PEM -f /path/to/your_key.pem

'''
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..databases.db import Base



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
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)



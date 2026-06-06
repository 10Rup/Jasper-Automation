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
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)




class Process(Base):
    __tablename__ = 'processimages'
    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(Integer, ForeignKey('uploads.id'), nullable=False)
    bandname = Column(String, nullable=False)
    path = Column(String, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)
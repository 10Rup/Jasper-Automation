from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .database import Base

class ApiMaster(Base):
    __tablename__ = 'apimaster'
    id = Column(Integer, primary_key=True, index=True)
    apiname = Column(String,index=True)
    username = Column(String, nullable=False)
    apikey = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

class Uploadfile(Base):
    __tablename__ = 'uploadfiles'
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String,index=True)
    filepath = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    isdeleted = Column(Boolean, default=False)

class CropImages(Base):
    __tablename__ = 'cropimages'
    id = Column(Integer, primary_key=True, index=True)
    uploadfile_id = Column(Integer, ForeignKey('uploadfiles.id'), nullable=False)
    bandname = Column(String, nullable=False)
    filepath = Column(String, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)


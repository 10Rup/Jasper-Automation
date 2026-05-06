from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
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
    displayname = Column(String,index=True)
    filename = Column(String,index=True)
    filetype = Column(String,index=True)
    filepath = Column(String, nullable=False)
    pagesize = Column(String)
    pagedimention = Column(String)
    report_query = Column(Text, default="")
    fields = Column(Text, default="")
    queryString = Column(Text, default="")
    title = Column(Text, default="")
    pageHeader = Column(Text, default="")
    columnHeader = Column(Text, default="")
    detail = Column(Text, default="")
    columnFooter = Column(Text, default="")
    pageFooter = Column(Text, default="")
    summary = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

class CropImages(Base):
    __tablename__ = 'cropimages'
    id = Column(Integer, primary_key=True, index=True)
    uploadfile_id = Column(Integer, ForeignKey('uploadfiles.id'), nullable=False)
    bandname = Column(String, nullable=False)
    filepath = Column(String, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

class XmlCode(Base):
    __tablename__ = 'xmlcodes'
    id = Column(Integer, primary_key=True, index=True)
    crop_id = Column(Integer, ForeignKey('cropimages.id'), nullable=False)
    bandname = Column(String, default="")
    codes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

class BandMst(Base):
    __tablename__ = 'bandmsts'
    id = Column(Integer, primary_key=True, index=True)
    bandname = Column(String, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)


class CompileReport(Base):
    __tablename__ = 'compilereports'
    id = Column(Integer, primary_key=True, index=True)
    uploadfile_id = Column(Integer, ForeignKey('uploadfiles.id'), nullable=False)
    filename = Column(String,index=True)
    is_processed = Column(Boolean, default=False)
    download_filepath = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)
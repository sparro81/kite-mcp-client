# models.py
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(SQLAlchemyBaseUserTable[int], Base):
    id = Column(Integer, primary_key=True)
    holdings = relationship("Holding", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", uselist=False, cascade="all, delete-orphan")
    cached_news = relationship("CachedNews", back_populates="user", cascade="all, delete-orphan")

class Holding(Base):
    __tablename__ = "holdings"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    average_price = Column(Float, nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"))
    user = relationship("User", back_populates="holdings")

class APIKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True)
    brave_key = Column(String) # In a real app, encrypt these!
    openai_key = Column(String) # In a real app, encrypt these!
    user_id = Column(Integer, ForeignKey("user.id"), unique=True)
    user = relationship("User", back_populates="api_keys")

class CachedNews(Base):
    __tablename__ = "cached_news"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    articles = Column(JSON, nullable=False)
    timestamp = Column(DateTime, server_default=func.now(), onupdate=func.now())
    user_id = Column(Integer, ForeignKey("user.id"))
    user = relationship("User", back_populates="cached_news")

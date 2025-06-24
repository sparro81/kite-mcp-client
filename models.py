# models.py

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.orm import DeclarativeBase
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
# define your Base here
class Base(DeclarativeBase):
    pass  

# 1) Subclass Base *and* SQLAlchemyBaseUserTable[int]
class User(Base, SQLAlchemyBaseUserTable[int]):
    # SQLAlchemyBaseUserTable already gives you:
    #   __tablename__ = "user"
    #   id = Column(Integer, primary_key=True)
    #   email, hashed_password, is_active, ...
    # so just add your relationships.
    holdings     = relationship("Holding",    back_populates="user", cascade="all, delete-orphan")
    api_keys     = relationship("APIKey",     back_populates="user", uselist=False, cascade="all, delete-orphan")
    cached_news  = relationship("CachedNews", back_populates="user", cascade="all, delete-orphan")


# 2) All other tables must subclass Base so metadata is tracked:
class Holding(Base):
    __tablename__ = "holdings"

    id            = Column(Integer, primary_key=True)
    symbol        = Column(String, nullable=False)
    quantity      = Column(Float, nullable=False)
    average_price = Column(Float, nullable=False)

    user_id = Column(Integer, ForeignKey("user.id"))
    user    = relationship("User", back_populates="holdings")


class APIKey(Base):
    __tablename__ = "api_keys"

    id         = Column(Integer, primary_key=True)
    brave_key  = Column(String, nullable=False)
    openai_key = Column(String, nullable=False)

    user_id = Column(Integer, ForeignKey("user.id"), unique=True)
    user    = relationship("User", back_populates="api_keys")


class CachedNews(Base):
    __tablename__ = "cached_news"

    id        = Column(Integer, primary_key=True)
    symbol    = Column(String, nullable=False, index=True)
    articles  = Column(JSON,   nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        server_onupdate=func.now()
    )

    user_id = Column(Integer, ForeignKey("user.id"))
    user    = relationship("User", back_populates="cached_news")

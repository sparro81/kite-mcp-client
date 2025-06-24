# database.py
import os
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import (AsyncSession, AsyncAttrs,
                                    create_async_engine)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from models import User # Import User model

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

class Base(AsyncAttrs, DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass

# Create the async engine for the database connection.
engine = create_async_engine(DATABASE_URL)
# Create a session maker for creating new database sessions.
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def create_db_and_tables():
    """
    Initializes the database by creating all tables defined in models.py.
    This is called by the preDeployCommand in render.yaml.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get an async database session for a request.
    """
    async with async_session_maker() as session:
        yield session

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    """
    Dependency for fastapi-users to interact with the User model in the database.
    """
    yield SQLAlchemyUserDatabase(session, User)
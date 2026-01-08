import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("POSTGRES_USER", "admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin123")
DB_NAME = os.getenv("POSTGRES_DB", "greenfield_auth_db")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Creazione del motore di connessione al database
engine = create_async_engine(DATABASE_URL, echo=True, pool_size=20)

# Creazione della sessione asincrona
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Base class per i modelli ORM
Base = declarative_base()

# Dipendenza per ottenere una sessione, per poter interagire con il database negli endpoint
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
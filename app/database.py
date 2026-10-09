

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine_kwargs = {"echo": (settings.app_env == "development")}
if not settings.database_url.startswith("sqlite"):
    engine_kwargs.update({"pool_size": 5, "max_overflow": 5})

engine = create_async_engine(settings.database_url, **engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:  
    """FastAPI dependency — yields one session per request."""
    async with async_session() as session:
        yield session

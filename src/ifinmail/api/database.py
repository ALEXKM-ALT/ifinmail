from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ifinmail.api.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

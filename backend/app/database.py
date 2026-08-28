# to set up the connection to postgres and hands out db sessions . local for now

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit = False, autoflush=False, bind=engine)

Basr = declarative_base()

def get_db():
    db= SessionLocal()
    try:
        yield db
    finally:
        db.close()
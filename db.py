from sqlalchemy import create_engine
from settings import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

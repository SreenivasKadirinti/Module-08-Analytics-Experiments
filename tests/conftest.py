import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.connection import Base
from app.models import tables  # noqa: F401  (registers models)

TEST_DB_URL = os.getenv("TEST_DATABASE_URL")

@pytest.fixture()
def db():
    if not TEST_DB_URL:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated test database")
    engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
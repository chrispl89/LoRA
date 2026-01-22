"""
Pytest configuration and fixtures.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.db.base import Base
from app.main import app
from app.api.dependencies import get_db


@pytest.fixture(scope="function")
def db():
    """Create test database session."""
    # Use SQLite for tests so local Postgres is not required.
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create test client."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _stub_s3(monkeypatch):
    """
    Prevent tests from connecting to MinIO.
    """

    class _FakeS3:
        def generate_presigned_put_url(self, key: str, content_type: str, expiration: int = None):
            return {"url": f"http://example.invalid/put/{key}", "method": "PUT", "key": key, "content_type": content_type}

        def generate_presigned_get_url(self, key: str, expiration: int = None):
            return f"http://example.invalid/get/{key}"

        def delete_file(self, s3_key: str):
            return None

        def delete_prefix(self, prefix: str):
            return None

    # Patch where it's imported/used
    import app.api.v1.persons as persons_mod
    import app.api.v1.generations as gens_mod

    monkeypatch.setattr(persons_mod, "get_s3_service", lambda: _FakeS3())
    monkeypatch.setattr(gens_mod, "get_s3_service", lambda: _FakeS3())

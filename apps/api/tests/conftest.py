import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app, conversation_agent
from packages.domain.database import Base, get_session
from packages.domain.seed import seed_database


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "console")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with testing_session() as session:
        seed_database(session)

    def override_session():
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    conversation_agent.reset()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

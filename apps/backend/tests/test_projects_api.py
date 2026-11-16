import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db_session
from app.core.config import Settings
from app.database.models import Base
from app.main import create_app


@pytest.fixture
def test_app():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app(Settings(_env_file=None, environment="test", database_url=None, redis_url=None))
    app.dependency_overrides[get_db_session] = override_get_db_session

    yield app

    Base.metadata.drop_all(bind=engine)


def test_project_api_lifecycle(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                # 1. Initially empty
                r_list = await client.get("/api/v1/projects")
                assert r_list.status_code == 200
                assert r_list.json() == {"items": [], "total": 0}

                # 2. Create project
                payload = {
                    "name": "Part-Time Jobs App",
                    "description": "Android part-time jobs app for student employment.",
                    "category": "mobile_app",
                    "target_audience": "University students seeking flexible hours",
                    "metadata": {"package_name": "com.example.parttimejobs"},
                }
                r_create = await client.post("/api/v1/projects", json=payload)
                assert r_create.status_code == 201
                created = r_create.json()
                assert created["name"] == "Part-Time Jobs App"
                assert created["slug"] == "part-time-jobs-app"
                assert created["status"] == "active"
                assert created["category"] == "mobile_app"
                project_id = created["id"]

                # 3. Get by ID and Slug
                r_get_id = await client.get(f"/api/v1/projects/{project_id}")
                assert r_get_id.status_code == 200
                assert r_get_id.json()["id"] == project_id

                r_get_slug = await client.get("/api/v1/projects/part-time-jobs-app")
                assert r_get_slug.status_code == 200
                assert r_get_slug.json()["id"] == project_id

                # 4. Update
                r_update = await client.patch(
                    f"/api/v1/projects/{project_id}",
                    json={"status": "paused", "name": "Part-Time Jobs Platform"},
                )
                assert r_update.status_code == 200
                assert r_update.json()["status"] == "paused"
                assert r_update.json()["name"] == "Part-Time Jobs Platform"

                # 5. Delete
                r_delete = await client.delete(f"/api/v1/projects/{project_id}")
                assert r_delete.status_code == 204

                # 6. Verify 404 after delete
                r_verify_del = await client.get(f"/api/v1/projects/{project_id}")
                assert r_verify_del.status_code == 404
                assert r_verify_del.json()["error"]["code"] == "not_found"

    asyncio.run(run())

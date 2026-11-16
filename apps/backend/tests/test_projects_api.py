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
                data = r_list.json()
                assert data["items"] == []
                assert data["total"] == 0
                assert data["limit"] == 50
                assert data["offset"] == 0

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


def test_project_api_validation_errors(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                # 1. Empty name
                r_empty = await client.post("/api/v1/projects", json={"name": ""})
                assert r_empty.status_code == 422
                assert r_empty.json()["error"]["code"] == "validation_error"

                # 2. Invalid category
                r_cat = await client.post(
                    "/api/v1/projects",
                    json={"name": "Valid Name", "category": "non_existent_category"},
                )
                assert r_cat.status_code == 422
                assert r_cat.json()["error"]["code"] == "validation_error"

                # 3. Invalid slug format (uppercase, spaces, symbols)
                r_slug = await client.post(
                    "/api/v1/projects",
                    json={"name": "Valid Name", "slug": "Invalid Slug!"},
                )
                assert r_slug.status_code == 422
                assert r_slug.json()["error"]["code"] == "validation_error"

                # 4. Out-of-range pagination parameters
                r_limit_high = await client.get("/api/v1/projects?limit=201")
                assert r_limit_high.status_code == 422

                r_limit_low = await client.get("/api/v1/projects?limit=0")
                assert r_limit_low.status_code == 422

                r_offset_neg = await client.get("/api/v1/projects?offset=-1")
                assert r_offset_neg.status_code == 422

    asyncio.run(run())


def test_project_api_pagination_and_filters(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                # Create 5 projects (3 active mobile, 2 paused saas)
                for i in range(3):
                    await client.post(
                        "/api/v1/projects",
                        json={"name": f"Mobile {i}", "category": "mobile_app"},
                    )
                for i in range(2):
                    res = await client.post(
                        "/api/v1/projects",
                        json={"name": f"SaaS {i}", "category": "saas"},
                    )
                    pid = res.json()["id"]
                    await client.patch(f"/api/v1/projects/{pid}", json={"status": "paused"})

                # Test total count and pagination limit
                r_page1 = await client.get("/api/v1/projects?limit=2&offset=0")
                assert r_page1.status_code == 200
                data1 = r_page1.json()
                assert data1["total"] == 5
                assert len(data1["items"]) == 2
                assert data1["limit"] == 2
                assert data1["offset"] == 0

                # Test offset
                r_page2 = await client.get("/api/v1/projects?limit=2&offset=2")
                assert r_page2.status_code == 200
                data2 = r_page2.json()
                assert data2["total"] == 5
                assert len(data2["items"]) == 2
                assert data2["offset"] == 2

                # Test filter by status
                r_paused = await client.get("/api/v1/projects?status=paused")
                assert r_paused.status_code == 200
                data_paused = r_paused.json()
                assert data_paused["total"] == 2
                assert all(item["status"] == "paused" for item in data_paused["items"])

                # Test filter by category
                r_mobile = await client.get("/api/v1/projects?category=mobile_app")
                assert r_mobile.status_code == 200
                data_mobile = r_mobile.json()
                assert data_mobile["total"] == 3
                assert all(item["category"] == "mobile_app" for item in data_mobile["items"])

    asyncio.run(run())


def test_project_api_conflict_and_missing_handling(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                # 1. Duplicate slug conflict
                r1 = await client.post(
                    "/api/v1/projects",
                    json={"name": "Project One", "slug": "shared-slug"},
                )
                assert r1.status_code == 201

                r2 = await client.post(
                    "/api/v1/projects",
                    json={"name": "Project Two", "slug": "shared-slug"},
                )
                assert r2.status_code == 409
                err2 = r2.json()["error"]
                assert err2["code"] == "conflict"
                assert "already exists" in err2["message"]

                # 2. Update non-existent project -> 404
                r_up = await client.patch(
                    "/api/v1/projects/non-existent-id",
                    json={"name": "Updated Name"},
                )
                assert r_up.status_code == 404
                assert r_up.json()["error"]["code"] == "not_found"

                # 3. Delete non-existent project -> 404
                r_del = await client.delete("/api/v1/projects/non-existent-id")
                assert r_del.status_code == 404
                assert r_del.json()["error"]["code"] == "not_found"

    asyncio.run(run())

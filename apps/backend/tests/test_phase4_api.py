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


def test_research_api_endpoints(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                # 1. Create a project
                p_res = await client.post("/api/v1/projects", json={"name": "API Test Project"})
                assert p_res.status_code == 201
                project_id = p_res.json()["id"]

                # 2. Initially empty research list
                r_list = await client.get(f"/api/v1/projects/{project_id}/research")
                assert r_list.status_code == 200
                assert r_list.json()["items"] == []

                # 3. Create research record
                r_create = await client.post(
                    f"/api/v1/projects/{project_id}/research",
                    json={
                        "title": "Store reviews report checkout hang",
                        "source_type": "app_review",
                        "source_name": "Play Store",
                        "source_quote": "App spins for 30s during checkout",
                        "observation_summary": "Users encounter checkout hang on Android",
                        "metadata": {"rating": 1},
                    },
                )
                assert r_create.status_code == 201
                rec = r_create.json()
                rec_id = rec["id"]
                assert rec["source_type"] == "app_review"
                assert rec["metadata"] == {"rating": 1}

                # 4. Get by ID
                r_get = await client.get(f"/api/v1/projects/{project_id}/research/{rec_id}")
                assert r_get.status_code == 200
                assert r_get.json()["id"] == rec_id

                # 5. Patch research record
                r_patch = await client.patch(
                    f"/api/v1/projects/{project_id}/research/{rec_id}",
                    json={"title": "Updated Play Store Review Title"},
                )
                assert r_patch.status_code == 200
                assert r_patch.json()["title"] == "Updated Play Store Review Title"

    asyncio.run(run())


def test_opportunity_and_association_api(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                # 1. Create project
                p_res = await client.post("/api/v1/projects", json={"name": "Opportunity API Project"})
                project_id = p_res.json()["id"]

                # 2. Create research record
                r_res = await client.post(
                    f"/api/v1/projects/{project_id}/research",
                    json={
                        "title": "Analytics funnel drop-off",
                        "source_type": "analytics",
                        "evidence_data": {"dropoff_pct": 55},
                        "observation_summary": "55% drop off at address entry",
                    },
                )
                research_id = r_res.json()["id"]

                # 3. Create opportunity
                opp_res = await client.post(
                    f"/api/v1/projects/{project_id}/opportunities",
                    json={
                        "title": "Address Autocomplete",
                        "problem_statement": "Manual address typing causes drop-off.",
                        "hypothesis": "If we add autocomplete, checkout rate increases 15%.",
                        "proposed_mechanism": "Google Places API integration.",
                        "target_audience": "Mobile checkout users",
                        "category": "activation",
                        "estimated_impact": "high",
                        "estimated_effort": "low",
                        "confidence_score": 0.8,
                    },
                )
                assert opp_res.status_code == 201
                opp = opp_res.json()
                opp_id = opp["id"]
                assert opp["status"] == "draft"
                assert opp["priority"] == "p0_urgent"

                # 4. Associate research with opportunity
                assoc_res = await client.post(
                    f"/api/v1/projects/{project_id}/opportunities/{opp_id}/research",
                    json={
                        "items": [
                            {"research_id": research_id, "notes": "Funnel metrics confirm the dropoff location."}
                        ]
                    },
                )
                assert assoc_res.status_code == 200
                assert assoc_res.json()["linked_count"] == 1

                # 5. List associated research
                linked_res = await client.get(
                    f"/api/v1/projects/{project_id}/opportunities/{opp_id}/research"
                )
                assert linked_res.status_code == 200
                links = linked_res.json()
                assert len(links) == 1
                assert links[0]["research_id"] == research_id
                assert links[0]["notes"] == "Funnel metrics confirm the dropoff location."
                assert links[0]["research"]["title"] == "Analytics funnel drop-off"

                # 6. Execute lifecycle transition
                trans_res = await client.post(
                    f"/api/v1/projects/{project_id}/opportunities/{opp_id}/transition",
                    json={"status": "in_review", "reason": "Ready for team review"},
                )
                assert trans_res.status_code == 200
                assert trans_res.json()["status"] == "in_review"

                # 7. Get history
                hist_res = await client.get(
                    f"/api/v1/projects/{project_id}/opportunities/{opp_id}/history"
                )
                assert hist_res.status_code == 200
                history_items = hist_res.json()["items"]
                assert len(history_items) == 2
                assert history_items[0]["new_status"] == "draft"
                assert history_items[1]["new_status"] == "in_review"

                # 8. Unlink research
                del_link = await client.delete(
                    f"/api/v1/projects/{project_id}/opportunities/{opp_id}/research/{research_id}"
                )
                assert del_link.status_code == 204

    asyncio.run(run())

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
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
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


def test_strategy_api_full_lifecycle(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                # 1. Create a project
                p_res = await client.post("/api/v1/projects", json={"name": "Strategy API Project"})
                assert p_res.status_code == 201
                proj_id = p_res.json()["id"]

                # 2. Initially empty strategy list
                list_res = await client.get(f"/api/v1/projects/{proj_id}/strategies")
                assert list_res.status_code == 200
                assert list_res.json()["items"] == []

                # 3. Create strategy
                create_res = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies",
                    json={
                        "name": "Q1 Student Activation",
                        "strategic_vision": "Double first-week engagement with one-tap apply",
                        "target_audience": "University job seekers",
                        "strategic_constraints": "Zero paid channels; brand safety approval required",
                        "budget_envelope": 5000.0,
                        "currency": "USD",
                        "time_horizon": "Q1_2027",
                    },
                )
                assert create_res.status_code == 201
                strat = create_res.json()
                strat_id = strat["id"]
                assert strat["name"] == "Q1 Student Activation"
                assert strat["slug"] == "q1-student-activation"
                assert strat["status"] == "draft"
                assert strat["budget_envelope"] == 5000.0
                assert strat["currency"] == "USD"

                # 4. Get by ID and by slug
                get_by_id = await client.get(f"/api/v1/projects/{proj_id}/strategies/{strat_id}")
                assert get_by_id.status_code == 200
                assert get_by_id.json()["id"] == strat_id

                get_by_slug = await client.get(f"/api/v1/projects/{proj_id}/strategies/q1-student-activation")
                assert get_by_slug.status_code == 200
                assert get_by_slug.json()["id"] == strat_id

                # 5. Verify initial history is empty for untransitioned draft
                hist_res = await client.get(f"/api/v1/projects/{proj_id}/strategies/{strat_id}/history")
                assert hist_res.status_code == 200
                history = hist_res.json()["items"]
                assert len(history) == 0

                # 6. Update strategy (PATCH)
                patch_res = await client.patch(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}",
                    json={"description": "Updated platform roadmap description", "budget_envelope": 6000.0},
                )
                assert patch_res.status_code == 200
                assert patch_res.json()["description"] == "Updated platform roadmap description"
                assert patch_res.json()["budget_envelope"] == 6000.0

                # 7. Attempt to update status via PATCH is blocked
                bad_patch = await client.patch(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}",
                    json={"status": "approved"},
                )
                assert bad_patch.status_code == 409

                # 8. Transition to in_review (creates first history record)
                t1 = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/transition",
                    json={"status": "in_review"},
                )
                assert t1.status_code == 200
                assert t1.json()["status"] == "in_review"

                hist_t1 = await client.get(f"/api/v1/projects/{proj_id}/strategies/{strat_id}/history")
                assert len(hist_t1.json()["items"]) == 1
                assert hist_t1.json()["items"][0]["previous_status"] == "draft"
                assert hist_t1.json()["items"][0]["new_status"] == "in_review"

                # 9. Demote back to draft requires explanation
                no_reason = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/transition",
                    json={"status": "draft"},
                )
                assert no_reason.status_code == 422

                revert = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/transition",
                    json={"status": "draft", "reason": "Requires further TAM validation before signoff"},
                )
                assert revert.status_code == 200
                assert revert.json()["status"] == "draft"

                # 10. Cannot delete strategy that has transition history
                del_blocked = await client.delete(f"/api/v1/projects/{proj_id}/strategies/{strat_id}")
                assert del_blocked.status_code == 409

                # 11. Untransitioned draft strategy can be deleted
                disp_res = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies",
                    json={
                        "name": "Disposable Draft API",
                        "strategic_vision": "Temporary experiment",
                        "target_audience": "Beta testers",
                        "time_horizon": "Q1",
                    },
                )
                assert disp_res.status_code == 201
                disp_id = disp_res.json()["id"]

                del_disp = await client.delete(f"/api/v1/projects/{proj_id}/strategies/{disp_id}")
                assert del_disp.status_code == 204

                get_disp = await client.get(f"/api/v1/projects/{proj_id}/strategies/{disp_id}")
                assert get_disp.status_code == 404

    asyncio.run(run())


def test_goal_api_and_metric_progress(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                p_res = await client.post("/api/v1/projects", json={"name": "Goal API Project"})
                proj_id = p_res.json()["id"]

                s_res = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies",
                    json={
                        "name": "Retention Strategy",
                        "strategic_vision=" : "Keep students active",
                        "strategic_vision": "Improve long term engagement",
                        "target_audience": "Students",
                        "time_horizon": "Q2_2027",
                    },
                )
                strat_id = s_res.json()["id"]

                # 1. Create goal
                g_res = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/goals",
                    json={
                        "name": "Day 7 Retention",
                        "description": "Increase 7-day retention",
                        "metric_name": "d7_retention_pct",
                        "metric_unit": "percent",
                        "baseline_value": 15.0,
                        "target_value": 30.0,
                    },
                )
                assert g_res.status_code == 201
                goal = g_res.json()
                goal_id = goal["id"]
                assert goal["current_value"] == 15.0
                assert goal["progress_percentage"] == 0.0
                assert goal["is_increasing_metric"] is True
                assert goal["status"] == "pending"

                # 2. List goals
                list_goals = await client.get(f"/api/v1/projects/{proj_id}/strategies/{strat_id}/goals")
                assert list_goals.status_code == 200
                assert len(list_goals.json()) == 1

                # 3. Record progress check-in #1
                p1_res = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/goals/{goal_id}/progress",
                    json={"new_value": 22.5, "notes": "Week 2 progress report"},
                )
                assert p1_res.status_code == 201
                rec1 = p1_res.json()
                assert rec1["previous_value"] == 15.0
                assert rec1["new_value"] == 22.5
                assert rec1["actor"] == "default"

                # Verify goal current_value and progress updated
                get_goal = await client.get(f"/api/v1/projects/{proj_id}/strategies/{strat_id}/goals/{goal_id}")
                assert get_goal.status_code == 200
                assert get_goal.json()["current_value"] == 22.5
                assert get_goal.json()["progress_percentage"] == 50.0
                assert get_goal.json()["status"] == "on_track"

                # 4. Get metric history
                history = await client.get(f"/api/v1/projects/{proj_id}/strategies/{strat_id}/goals/{goal_id}/progress")
                assert history.status_code == 200
                assert len(history.json()) == 1

                # 5. Delete goal with history is blocked
                del_goal = await client.delete(f"/api/v1/projects/{proj_id}/strategies/{strat_id}/goals/{goal_id}")
                assert del_goal.status_code == 409

    asyncio.run(run())


def test_strategy_opportunity_association_api(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                p_res = await client.post("/api/v1/projects", json={"name": "Assoc API Project"})
                proj_id = p_res.json()["id"]

                s_res = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies",
                    json={
                        "name": "Assoc Strategy",
                        "strategic_vision": "Vision",
                        "target_audience": "Audience",
                        "time_horizon": "Q1",
                    },
                )
                strat_id = s_res.json()["id"]

                # Create opportunity and advance to in_review
                o_res = await client.post(
                    f"/api/v1/projects/{proj_id}/opportunities",
                    json={
                        "title": "One-Tap Apply",
                        "problem_statement": "Problem",
                        "hypothesis": "Hypothesis",
                        "proposed_mechanism": "Mechanism",
                        "target_audience": "Students",
                        "category": "activation",
                    },
                )
                opp_id = o_res.json()["id"]

                # Attempt to link opportunity in draft to draft strategy is rejected (422)
                bad_link = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/opportunities",
                    json={"items": [{"opportunity_id": opp_id}]},
                )
                assert bad_link.status_code == 422

                # Move opportunity to in_review
                await client.post(
                    f"/api/v1/projects/{proj_id}/opportunities/{opp_id}/transition",
                    json={"status": "in_review"},
                )

                # Linking in_review opportunity to draft strategy now succeeds
                link_res = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/opportunities",
                    json={"items": [{"opportunity_id": opp_id, "strategic_rationale": "Key activation mechanism"}]},
                )
                assert link_res.status_code == 200
                assert len(link_res.json()) == 1
                assert link_res.json()[0]["strategic_rationale"] == "Key activation mechanism"

                # List linked opportunities
                list_assoc = await client.get(f"/api/v1/projects/{proj_id}/strategies/{strat_id}/opportunities")
                assert list_assoc.status_code == 200
                assert len(list_assoc.json()) == 1
                assert list_assoc.json()[0]["opportunity"]["title"] == "One-Tap Apply"

                # Strategy submission to in_review succeeds
                await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/transition",
                    json={"status": "in_review"},
                )

                # Strategy approval is blocked because linked opportunity is still only in_review!
                approve_blocked = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/transition",
                    json={"status": "approved"},
                )
                assert approve_blocked.status_code == 422

                # Approve the opportunity
                await client.post(
                    f"/api/v1/projects/{proj_id}/opportunities/{opp_id}/transition",
                    json={"status": "approved"},
                )

                # Now strategy approval succeeds
                approve_ok = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/transition",
                    json={"status": "approved"},
                )
                assert approve_ok.status_code == 200
                assert approve_ok.json()["status"] == "approved"

                # Unlink opportunity
                unlink = await client.delete(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/opportunities/{opp_id}"
                )
                assert unlink.status_code == 204

    asyncio.run(run())


def test_cross_project_api_isolation(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                p1_res = await client.post("/api/v1/projects", json={"name": "Project Alpha"})
                p1_id = p1_res.json()["id"]

                p2_res = await client.post("/api/v1/projects", json={"name": "Project Beta"})
                p2_id = p2_res.json()["id"]

                s1_res = await client.post(
                    f"/api/v1/projects/{p1_id}/strategies",
                    json={
                        "name": "Alpha Strategy",
                        "strategic_vision": "Vision",
                        "target_audience": "Audience",
                        "time_horizon": "Q1",
                    },
                )
                s1_id = s1_res.json()["id"]

                # Accessing Project 1's strategy under Project 2's URL path must return 404
                cross_get = await client.get(f"/api/v1/projects/{p2_id}/strategies/{s1_id}")
                assert cross_get.status_code == 404

                # Cross-project goal creation attempt returns 404
                cross_goal = await client.post(
                    f"/api/v1/projects/{p2_id}/strategies/{s1_id}/goals",
                    json={
                        "name": "Illegal Goal",
                        "metric_name": "metric",
                        "metric_unit": "count",
                        "baseline_value": 0.0,
                        "target_value": 10.0,
                    },
                )
                assert cross_goal.status_code == 404

    asyncio.run(run())


def test_goal_status_history_api(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                p_res = await client.post("/api/v1/projects", json={"name": "Goal History API"})
                proj_id = p_res.json()["id"]

                s_res = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies",
                    json={
                        "name": "Hist Strategy",
                        "strategic_vision": "V",
                        "target_audience": "A",
                        "time_horizon": "Q1",
                    },
                )
                strat_id = s_res.json()["id"]

                # Second strategy in same project for cross-strategy 404 check
                s2_res = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies",
                    json={
                        "name": "Other Strategy",
                        "strategic_vision": "V",
                        "target_audience": "A",
                        "time_horizon": "Q1",
                    },
                )
                strat2_id = s2_res.json()["id"]

                g_res = await client.post(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/goals",
                    json={
                        "name": "G",
                        "metric_name": "m",
                        "metric_unit": "u",
                        "baseline_value": 1.0,
                        "target_value": 10.0,
                    },
                )
                assert g_res.status_code == 201
                goal_id = g_res.json()["id"]

                # Manual status change writes a second history entry
                u_res = await client.patch(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/goals/{goal_id}",
                    json={"status": "on_track", "reason": "manual check-in"},
                )
                assert u_res.status_code == 200

                hist = await client.get(
                    f"/api/v1/projects/{proj_id}/strategies/{strat_id}/goals/{goal_id}/history"
                )
                assert hist.status_code == 200
                items = hist.json()["items"]
                assert len(items) == 2
                assert items[0]["new_status"] == "pending"
                assert items[1]["new_status"] == "on_track"
                assert items[1]["previous_status"] == "pending"
                assert items[1]["reason"] == "manual check-in"
                assert "created_at" in items[0] and "actor" in items[0]

                # Cross-strategy access to the same goal returns 404
                wrong = await client.get(
                    f"/api/v1/projects/{proj_id}/strategies/{strat2_id}/goals/{goal_id}/history"
                )
                assert wrong.status_code == 404

    asyncio.run(run())

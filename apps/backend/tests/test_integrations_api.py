"""API-level tests for Phase 6 integration endpoints."""

import asyncio

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
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

    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=None,
        redis_url=None,
        credential_encryption_key=SecretStr(Fernet.generate_key().decode()),
    )
    app = create_app(settings)
    app.dependency_overrides[get_db_session] = override_get_db_session

    yield app

    Base.metadata.drop_all(bind=engine)


def test_integration_api_full_flow(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                p = (await client.post("/api/v1/projects", json={"name": "Int API"})).json()
                pid = p["id"]

                # Provider CRUD
                prov = await client.post(
                    f"/api/v1/projects/{pid}/integrations/providers",
                    json={"name": "Sandbox", "adapter_type": "sandbox"},
                )
                assert prov.status_code == 201
                prov_body = prov.json()
                assert prov_body["sandbox_only"] is True
                assert prov_body["has_credential"] is False
                provider_id = prov_body["id"]

                # Credential is write-only
                cred = await client.put(
                    f"/api/v1/projects/{pid}/integrations/providers/{provider_id}/credential",
                    json={"credential": '{"api_key":"s3cret"}'},
                )
                assert cred.status_code == 204
                prov2 = await client.get(
                    f"/api/v1/projects/{pid}/integrations/providers/{provider_id}"
                )
                assert prov2.json()["has_credential"] is True
                assert "s3cret" not in str(prov2.json())

                # Action lifecycle
                act = await client.post(
                    f"/api/v1/projects/{pid}/integrations/providers/{provider_id}/actions",
                    json={"action_type": "announce", "payload": {"msg": "hi"}, "idempotency_key": "k1"},
                )
                assert act.status_code == 201
                action = act.json()
                assert action["status"] == "pending_approval"
                aid = action["id"]

                # Idempotent replay returns the same action
                replay = await client.post(
                    f"/api/v1/projects/{pid}/integrations/providers/{provider_id}/actions",
                    json={"action_type": "announce", "payload": {"msg": "hi"}, "idempotency_key": "k1"},
                )
                assert replay.json()["id"] == aid

                # Execute before approval -> 409
                early = await client.post(
                    f"/api/v1/projects/{pid}/integrations/actions/{aid}/execute"
                )
                assert early.status_code == 409

                # Approve then execute
                ap = await client.post(
                    f"/api/v1/projects/{pid}/integrations/actions/{aid}/approve",
                    json={"reason": "approved for test"},
                )
                assert ap.status_code == 200
                assert ap.json()["status"] == "approved"
                assert ap.json()["approver"] == "default"
                assert ap.json()["approval_expires_at"] is not None

                ex = await client.post(
                    f"/api/v1/projects/{pid}/integrations/actions/{aid}/execute"
                )
                assert ex.status_code == 200
                assert ex.json()["status"] == "succeeded"
                assert ex.json()["result"]["adapter"] == "sandbox"

                # Audit reads
                events = await client.get(
                    f"/api/v1/projects/{pid}/integrations/actions/{aid}/events"
                )
                assert [e["event_type"] for e in events.json()] == [
                    "submitted", "approved", "executing", "succeeded"
                ]
                calls = await client.get(
                    f"/api/v1/projects/{pid}/integrations/actions/{aid}/calls"
                )
                assert calls.json()[0]["mode"] == "sandbox"

                # Second execute -> 409
                again = await client.post(
                    f"/api/v1/projects/{pid}/integrations/actions/{aid}/execute"
                )
                assert again.status_code == 409

    asyncio.run(run())


def test_integration_api_scoping_and_guards(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                p1 = (await client.post("/api/v1/projects", json={"name": "P1"})).json()
                p2 = (await client.post("/api/v1/projects", json={"name": "P2"})).json()

                prov = await client.post(
                    f"/api/v1/projects/{p1['id']}/integrations/providers",
                    json={"name": "S", "adapter_type": "sandbox"},
                )
                pid_prov = prov.json()["id"]

                act = await client.post(
                    f"/api/v1/projects/{p1['id']}/integrations/providers/{pid_prov}/actions",
                    json={"action_type": "t", "payload": {}},
                )
                aid = act.json()["id"]

                # Cross-project access -> 404
                cross = await client.get(
                    f"/api/v1/projects/{p2['id']}/integrations/actions/{aid}"
                )
                assert cross.status_code == 404
                cross_exec = await client.post(
                    f"/api/v1/projects/{p2['id']}/integrations/actions/{aid}/execute"
                )
                assert cross_exec.status_code == 404

                # Provider with actions cannot be deleted -> 409
                dele = await client.delete(
                    f"/api/v1/projects/{p1['id']}/integrations/providers/{pid_prov}"
                )
                assert dele.status_code == 409

                # Disabled provider rejects new actions -> 409
                await client.patch(
                    f"/api/v1/projects/{p1['id']}/integrations/providers/{pid_prov}",
                    json={"enabled": False},
                )
                blocked = await client.post(
                    f"/api/v1/projects/{p1['id']}/integrations/providers/{pid_prov}/actions",
                    json={"action_type": "t2", "payload": {}},
                )
                assert blocked.status_code == 409

                # Unknown adapter type -> 422
                bad = await client.post(
                    f"/api/v1/projects/{p1['id']}/integrations/providers",
                    json={"name": "Bad", "adapter_type": "does-not-exist"},
                )
                assert bad.status_code == 422

    asyncio.run(run())

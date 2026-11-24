"""Phase 6 integration adapter tests — service level (SQLite) and API level."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import (
    ApplicationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    UnprocessableEntityError,
)
from app.database.models import (
    Base,
    IntegrationAction,
    IntegrationActionEvent,
    IntegrationCallLog,
)
from app.integrations.codec import CredentialCodec
from app.schemas.integration import (
    IntegrationActionCreate,
    IntegrationProviderCreate,
    IntegrationProviderUpdate,
)
from app.schemas.project import ProjectCreate
from app.services.integration import IntegrationService
from app.services.project import ProjectService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def project(db_session):
    return ProjectService(db_session).create_project(ProjectCreate(name="Int Project"))


@pytest.fixture
def codec():
    return CredentialCodec(Fernet.generate_key().decode())


@pytest.fixture
def service(db_session, codec):
    return IntegrationService(db_session, credential_codec=codec, approval_ttl_seconds=3600)


def _provider(service, project, **kwargs):
    data = IntegrationProviderCreate(name="SandboxCo", adapter_type="sandbox", **kwargs)
    return service.create_provider(data, project_id=project.id)


def _action(service, provider, project, payload=None, **kwargs):
    data = IntegrationActionCreate(
        action_type="post_update",
        payload=payload if payload is not None else {"text": "hello"},
        **kwargs,
    )
    return service.create_action(provider.id, data, project_id=project.id, actor="test")


class TestProviderManagement:
    def test_create_and_list_provider(self, service, project):
        p = _provider(service, project)
        assert p.adapter_type == "sandbox"
        assert p.sandbox_only is True
        assert p.enabled is True
        assert service.list_providers(project.id)[0].id == p.id

    def test_get_provider_by_name(self, service, project):
        p = _provider(service, project)
        assert service.get_provider("SandboxCo", project.id).id == p.id

    def test_unknown_adapter_type_rejected(self, service, project):
        with pytest.raises(UnprocessableEntityError, match="Unknown adapter_type"):
            service.create_provider(
                IntegrationProviderCreate(name="X", adapter_type="nope"),
                project_id=project.id,
            )

    def test_duplicate_provider_name_rejected(self, service, project):
        _provider(service, project)
        with pytest.raises(ConflictError, match="already exists"):
            _provider(service, project)

    def test_update_provider(self, service, project):
        p = _provider(service, project)
        updated = service.update_provider(
            p.id, IntegrationProviderUpdate(enabled=False, rate_limit_per_minute=5), project.id
        )
        assert updated.enabled is False
        assert updated.rate_limit_per_minute == 5

    def test_cross_project_provider_is_404(self, service, project, db_session):
        p = _provider(service, project)
        other = ProjectService(db_session).create_project(ProjectCreate(name="Other"))
        with pytest.raises(NotFoundError):
            service.get_provider(p.id, other.id)


class TestCredentials:
    def test_set_credential_without_codec_fails_closed(self, db_session, project):
        svc = IntegrationService(db_session, credential_codec=None)
        p = svc.create_provider(
            IntegrationProviderCreate(name="S", adapter_type="sandbox"), project_id=project.id
        )
        with pytest.raises(ApplicationError, match="not configured"):
            svc.set_credential(p.id, "secret", project_id=project.id)

    def test_set_and_has_credential(self, service, project, db_session):
        p = _provider(service, project)
        assert service.has_credential(p.id, project.id) is False
        service.set_credential(p.id, '{"api_key":"abc"}', project_id=project.id)
        assert service.has_credential(p.id, project.id) is True
        # ciphertext must not equal plaintext and must decrypt correctly
        row = db_session.query(IntegrationCallLog)  # sanity: models importable
        from app.database.models import IntegrationCredential

        cred = db_session.query(IntegrationCredential).one()
        assert cred.ciphertext != '{"api_key":"abc"}'
        assert service._decrypt_credentials(p, project.id) == {"api_key": "abc"}


class TestActionLifecycle:
    def test_create_action_pending_with_event(self, service, project):
        p = _provider(service, project)
        action, created = _action(service, p, project)
        assert created is True
        assert action.status == "pending_approval"
        assert action.pending_approval_expires_at is not None
        assert len(action.payload_hash) == 64
        events = service.list_events(action.id, project.id)
        assert [e.event_type for e in events] == ["submitted"]

    def test_execute_unapproved_rejected(self, service, project):
        p = _provider(service, project)
        action, _ = _action(service, p, project)
        with pytest.raises(ConflictError, match="cannot be executed"):
            service.execute(action.id, project.id, "test")

    def test_full_lifecycle_succeeds(self, service, project):
        p = _provider(service, project)
        action, _ = _action(service, p, project)
        service.approve(action.id, project.id, "approver", "looks good")
        done = service.execute(action.id, project.id, "executor")
        assert done.status == "succeeded"
        assert done.result_json["adapter"] == "sandbox"
        assert done.result_json["echo"] == {"text": "hello"}
        assert done.attempt_count == 1
        calls = service.list_call_logs(action.id, project.id)
        assert len(calls) == 1
        assert calls[0].mode == "sandbox"
        assert calls[0].status == "succeeded"
        event_types = [e.event_type for e in service.list_events(action.id, project.id)]
        assert event_types == ["submitted", "approved", "executing", "succeeded"]

    def test_double_execute_blocked(self, service, project):
        p = _provider(service, project)
        action, _ = _action(service, p, project)
        service.approve(action.id, project.id, "a", None)
        service.execute(action.id, project.id, "e")
        with pytest.raises(ConflictError, match="cannot be executed"):
            service.execute(action.id, project.id, "e")
        assert service.get_action(action.id, project.id).attempt_count == 1

    def test_reject_and_cancel_paths(self, service, project):
        p = _provider(service, project)
        a1, _ = _action(service, p, project)
        service.reject(a1.id, project.id, "boss", "not now")
        assert service.get_action(a1.id, project.id).status == "rejected"
        with pytest.raises(ConflictError):
            service.execute(a1.id, project.id, "e")

        a2, _ = _action(service, p, project, payload={"text": "two"})
        service.cancel(a2.id, project.id, "owner", "changed mind")
        assert service.get_action(a2.id, project.id).status == "cancelled"

    def test_double_approve_blocked(self, service, project):
        p = _provider(service, project)
        action, _ = _action(service, p, project)
        service.approve(action.id, project.id, "a", None)
        with pytest.raises(ConflictError, match="cannot be approved"):
            service.approve(action.id, project.id, "b", None)

    def test_pending_expiry_blocks_approval(self, service, project, db_session):
        p = _provider(service, project)
        action, _ = _action(service, p, project)
        action.pending_approval_expires_at = action.pending_approval_expires_at.replace(
            year=2000
        )
        db_session.commit()
        with pytest.raises(ConflictError, match="expired"):
            service.approve(action.id, project.id, "a", None)
        assert service.get_action(action.id, project.id).status == "expired"

    def test_approval_expiry_blocks_execution(self, service, project, db_session):
        p = _provider(service, project)
        action, _ = _action(service, p, project)
        service.approve(action.id, project.id, "a", None)
        action.approval_expires_at = action.approval_expires_at.replace(year=2000)
        db_session.commit()
        with pytest.raises(ConflictError, match="expired"):
            service.execute(action.id, project.id, "e")
        assert service.get_action(action.id, project.id).status == "expired"


class TestIdempotency:
    def test_same_key_returns_existing(self, service, project):
        p = _provider(service, project)
        a1, c1 = _action(service, p, project, idempotency_key="k1")
        a2, c2 = _action(service, p, project, payload={"text": "changed"}, idempotency_key="k1")
        assert c1 is True and c2 is False
        assert a1.id == a2.id

    def test_no_key_allows_duplicates(self, service, project):
        p = _provider(service, project)
        _, c1 = _action(service, p, project)
        _, c2 = _action(service, p, project)
        assert c1 and c2


class TestRateLimit:
    def test_rate_limit_blocks_excess(self, service, project):
        p = _provider(service, project, rate_limit_per_minute=1)
        a1, _ = _action(service, p, project, payload={"n": 1})
        a2, _ = _action(service, p, project, payload={"n": 2})
        service.approve(a1.id, project.id, "a", None)
        service.approve(a2.id, project.id, "a", None)
        service.execute(a1.id, project.id, "e")
        with pytest.raises(RateLimitError):
            service.execute(a2.id, project.id, "e")


class TestSandboxEnforcement:
    def test_sandbox_only_provider_dispatches_sandbox_mode(self, service, project):
        p = _provider(service, project)  # sandbox_only=True default
        action, _ = _action(service, p, project)
        service.approve(action.id, project.id, "a", None)
        service.execute(action.id, project.id, "e")
        call = service.list_call_logs(action.id, project.id)[0]
        assert call.mode == "sandbox"

    def test_live_mode_for_non_sandbox_provider_still_uses_adapter(self, service, project):
        p = _provider(service, project, sandbox_only=False)
        action, _ = _action(service, p, project)
        service.approve(action.id, project.id, "a", None)
        service.execute(action.id, project.id, "e")
        call = service.list_call_logs(action.id, project.id)[0]
        assert call.mode == "live"
        assert service.get_action(action.id, project.id).status == "succeeded"


class TestProviderDeleteGuard:
    def test_provider_with_actions_cannot_be_deleted(self, service, project):
        p = _provider(service, project)
        _action(service, p, project)
        with pytest.raises(ConflictError, match="audit trail"):
            service.delete_provider(p.id, project.id)

    def test_provider_without_actions_deletes(self, service, project):
        p = _provider(service, project)
        service.delete_provider(p.id, project.id)
        with pytest.raises(NotFoundError):
            service.get_provider(p.id, project.id)


class TestProjectDeleteIntegrationBlockers:
    def test_project_with_integration_action_blocked(self, service, project, db_session):
        p = _provider(service, project)
        _action(service, p, project)
        with pytest.raises(ConflictError, match="integration action"):
            ProjectService(db_session).delete_project(project.id)

    def test_project_with_integration_credential_blocked(self, service, project, db_session):
        p = _provider(service, project)
        service.set_credential(p.id, '{"k":"v"}', project_id=project.id)
        with pytest.raises(ConflictError, match="integration credential"):
            ProjectService(db_session).delete_project(project.id)

    def test_project_with_bare_provider_still_deletes(self, service, project, db_session):
        _provider(service, project)
        ProjectService(db_session).delete_project(project.id)
        with pytest.raises(NotFoundError):
            ProjectService(db_session).get_project(project.id)

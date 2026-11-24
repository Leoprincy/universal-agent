from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import (
    AuthIdentity,
    get_current_identity,
    get_integration_service,
    get_project_service,
)
from app.schemas.integration import (
    CredentialSetInput,
    IntegrationActionCreate,
    IntegrationActionDecisionInput,
    IntegrationActionEventResponse,
    IntegrationActionListResponse,
    IntegrationActionResponse,
    IntegrationCallLogResponse,
    IntegrationProviderCreate,
    IntegrationProviderResponse,
    IntegrationProviderUpdate,
)
from app.services.integration import IntegrationService
from app.services.project import ProjectService

router = APIRouter()


def _provider_has_credential(service: IntegrationService, provider) -> bool:
    return service.has_credential(provider.id, provider.project_id)


def _to_provider_response(service: IntegrationService, p) -> IntegrationProviderResponse:
    return IntegrationProviderResponse(
        id=p.id,
        project_id=p.project_id,
        name=p.name,
        adapter_type=p.adapter_type,
        enabled=p.enabled,
        sandbox_only=p.sandbox_only,
        rate_limit_per_minute=p.rate_limit_per_minute,
        config=p.config_json,
        has_credential=_provider_has_credential(service, p),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _to_action_response(a) -> IntegrationActionResponse:
    return IntegrationActionResponse(
        id=a.id,
        project_id=a.project_id,
        provider_id=a.provider_id,
        action_type=a.action_type,
        payload=a.payload_json or {},
        payload_hash=a.payload_hash,
        status=a.status,
        idempotency_key=a.idempotency_key,
        actor=a.actor,
        approver=a.approver,
        decision_reason=a.decision_reason,
        pending_approval_expires_at=a.pending_approval_expires_at,
        approval_expires_at=a.approval_expires_at,
        decided_at=a.decided_at,
        executed_at=a.executed_at,
        attempt_count=a.attempt_count,
        result=a.result_json,
        error=a.error,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


# ── providers ──────────────────────────────────────────────────────────────


@router.get("/providers", response_model=list[IntegrationProviderResponse])
def list_providers(
    project_id_or_slug: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> list[IntegrationProviderResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    return [_to_provider_response(service, p) for p in service.list_providers(project.id)]


@router.post(
    "/providers",
    response_model=IntegrationProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_provider(
    project_id_or_slug: str,
    data: IntegrationProviderCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationProviderResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    provider = service.create_provider(data, project_id=project.id)
    return _to_provider_response(service, provider)


@router.get("/providers/{provider_id_or_name}", response_model=IntegrationProviderResponse)
def get_provider(
    project_id_or_slug: str,
    provider_id_or_name: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationProviderResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    provider = service.get_provider(provider_id_or_name, project_id=project.id)
    return _to_provider_response(service, provider)


@router.patch("/providers/{provider_id_or_name}", response_model=IntegrationProviderResponse)
def update_provider(
    project_id_or_slug: str,
    provider_id_or_name: str,
    data: IntegrationProviderUpdate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationProviderResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    provider = service.update_provider(provider_id_or_name, data, project_id=project.id)
    return _to_provider_response(service, provider)


@router.delete("/providers/{provider_id_or_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(
    project_id_or_slug: str,
    provider_id_or_name: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> Response:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    service.delete_provider(provider_id_or_name, project_id=project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/providers/{provider_id_or_name}/credential",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set provider credential (write-only, encrypted at rest)",
)
def set_credential(
    project_id_or_slug: str,
    provider_id_or_name: str,
    data: CredentialSetInput,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> Response:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    service.set_credential(provider_id_or_name, data.credential, project_id=project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── actions ────────────────────────────────────────────────────────────────


@router.get("/actions", response_model=IntegrationActionListResponse)
def list_actions(
    project_id_or_slug: str,
    provider_id: str | None = Query(None),
    action_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationActionListResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    items, total = service.list_actions(
        project_id=project.id,
        provider_id=provider_id,
        status=action_status,
        limit=limit,
        offset=offset,
    )
    return IntegrationActionListResponse(
        items=[_to_action_response(a) for a in items], total=total
    )


@router.post(
    "/providers/{provider_id_or_name}/actions",
    response_model=IntegrationActionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_action(
    project_id_or_slug: str,
    provider_id_or_name: str,
    data: IntegrationActionCreate,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationActionResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    action, _created = service.create_action(
        provider_id_or_name, data, project_id=project.id, actor=identity.owner
    )
    return _to_action_response(action)


@router.get("/actions/{action_id}", response_model=IntegrationActionResponse)
def get_action(
    project_id_or_slug: str,
    action_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationActionResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    return _to_action_response(service.get_action(action_id, project.id))


@router.post("/actions/{action_id}/approve", response_model=IntegrationActionResponse)
def approve_action(
    project_id_or_slug: str,
    action_id: str,
    data: IntegrationActionDecisionInput | None = None,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationActionResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    reason = data.reason if data else None
    return _to_action_response(
        service.approve(action_id, project.id, identity.owner, reason)
    )


@router.post("/actions/{action_id}/reject", response_model=IntegrationActionResponse)
def reject_action(
    project_id_or_slug: str,
    action_id: str,
    data: IntegrationActionDecisionInput | None = None,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationActionResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    reason = data.reason if data else None
    return _to_action_response(
        service.reject(action_id, project.id, identity.owner, reason)
    )


@router.post("/actions/{action_id}/cancel", response_model=IntegrationActionResponse)
def cancel_action(
    project_id_or_slug: str,
    action_id: str,
    data: IntegrationActionDecisionInput | None = None,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationActionResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    reason = data.reason if data else None
    return _to_action_response(
        service.cancel(action_id, project.id, identity.owner, reason)
    )


@router.post("/actions/{action_id}/execute", response_model=IntegrationActionResponse)
def execute_action(
    project_id_or_slug: str,
    action_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationActionResponse:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    return _to_action_response(
        service.execute(action_id, project.id, identity.owner)
    )


@router.get("/actions/{action_id}/events", response_model=list[IntegrationActionEventResponse])
def list_action_events(
    project_id_or_slug: str,
    action_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> list[IntegrationActionEventResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    return service.list_events(action_id, project.id)


@router.get("/actions/{action_id}/calls", response_model=list[IntegrationCallLogResponse])
def list_action_calls(
    project_id_or_slug: str,
    action_id: str,
    identity: AuthIdentity = Depends(get_current_identity),
    project_service: ProjectService = Depends(get_project_service),
    service: IntegrationService = Depends(get_integration_service),
) -> list[IntegrationCallLogResponse]:
    project = project_service.get_project(project_id_or_slug, owner=identity.owner)
    return service.list_call_logs(action_id, project.id)

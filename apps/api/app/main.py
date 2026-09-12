from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import UUID

from aria_observability import StructuredEventLogger, create_event_logger
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.errors import (
    AccountBootstrapFailedError,
    AccountContextRequiredError,
    AuthenticationProviderUnavailableError,
    AuthenticationRequiredError,
    ContextVersionRequiredError,
    CriticalGapsOpenError,
    DuplicateClarificationError,
    ForbiddenError,
    IdempotencyConflictError,
    InvalidClarificationStateError,
    InvalidContextItemStateError,
    InvalidRequirementStateError,
    MembershipRequiredError,
    ResourceNotFoundError,
    ScopeDraftStaleError,
    ScopeVersionUnchangedError,
    ValidationFailedError,
    VersionConflictError,
    account_bootstrap_failed_handler,
    account_context_required_handler,
    authentication_provider_unavailable_handler,
    authentication_required_handler,
    context_version_required_handler,
    critical_gaps_open_handler,
    duplicate_clarification_handler,
    forbidden_handler,
    idempotency_conflict_handler,
    invalid_clarification_state_handler,
    invalid_context_item_state_handler,
    invalid_requirement_state_handler,
    membership_required_handler,
    request_validation_handler,
    resource_not_found_handler,
    scope_draft_stale_handler,
    scope_version_unchanged_handler,
    validation_failed_handler,
    version_conflict_handler,
)
from app.api.middleware.observability import ObservabilityMiddleware
from app.api.routers.accounts import create_accounts_router
from app.api.routers.auth import create_auth_router
from app.api.routers.clarifications import create_clarifications_router
from app.api.routers.context_items import create_context_items_router
from app.api.routers.context_sources import create_context_sources_router
from app.api.routers.health import create_health_router
from app.api.routers.jobs import create_jobs_router
from app.api.routers.projects import create_projects_router
from app.api.routers.requirements import create_requirements_router
from app.api.routers.scope_drafts import create_scope_drafts_router
from app.api.routers.scope_versions import create_scope_versions_router
from app.core.config import ApiSettings, load_api_settings
from app.infrastructure.auth.supabase_jwt import (
    RejectingAccessTokenVerifier,
    SupabaseJwtVerifier,
)
from app.infrastructure.db.readiness import PostgresReadinessProbe, unavailable_database_probe
from app.infrastructure.db.runtime import DatabaseRuntime
from app.infrastructure.queue.readiness import RedisQueueReadinessProbe, unavailable_queue_probe
from app.modules.context.application.context_item_service import ContextItemReviewService
from app.modules.context.application.text_context_ingestion import CreateTextContextUseCase
from app.modules.context.infrastructure.context_item_repository import (
    SqlAlchemyContextItemUnitOfWorkFactory,
)
from app.modules.context.infrastructure.text_ingestion import (
    SqlAlchemyTextContextIngestionUnitOfWorkFactory,
)
from app.modules.gaps.application.clarification_service import ClarificationService
from app.modules.gaps.infrastructure.clarification_repository import (
    SqlAlchemyClarificationUnitOfWorkFactory,
)
from app.modules.identity.application.account_bootstrap import (
    AccountBootstrapContext,
    AccountBootstrapInfrastructureError,
    AccountBootstrapper,
    BootstrapAccountUseCase,
)
from app.modules.identity.application.account_discovery import AccountDiscovery
from app.modules.identity.application.ports import AccessTokenVerifier, AuthenticatedIdentity
from app.modules.identity.application.tenant_context import (
    ResolveTenantContextUseCase,
    TenantContext,
    TenantContextResolver,
)
from app.modules.identity.infrastructure.account_bootstrap import (
    SqlAlchemyAccountBootstrapUnitOfWorkFactory,
)
from app.modules.identity.infrastructure.account_discovery import SqlAlchemyAccountDiscovery
from app.modules.identity.infrastructure.membership_resolution import (
    SqlAlchemyMembershipResolver,
)
from app.modules.jobs.application.job_status import JobStatusApplicationService
from app.modules.jobs.infrastructure.repository import SqlAlchemyJobsUnitOfWorkFactory
from app.modules.projects.application.project_service import ProjectApplicationService
from app.modules.projects.infrastructure.repository import SqlAlchemyProjectUnitOfWorkFactory
from app.modules.requirements.application.requirement_crud_service import (
    RequirementCrudService,
)
from app.modules.requirements.infrastructure.repository import (
    SqlAlchemyRequirementCrudUnitOfWorkFactory,
)
from app.modules.scope.application.scope_draft_service import ScopeDraftService
from app.modules.scope.application.scope_version_service import ScopeVersionService
from app.modules.scope.infrastructure.repository import (
    SqlAlchemyScopeDraftUnitOfWorkFactory,
)
from app.modules.scope.infrastructure.version_repository import (
    SqlAlchemyScopeVersionUnitOfWorkFactory,
)


class UnavailableAccountBootstrapper:
    async def execute(self, identity: AuthenticatedIdentity) -> AccountBootstrapContext:
        del identity
        raise AccountBootstrapInfrastructureError


class UnavailableTenantContextResolver:
    async def execute(
        self,
        identity: AuthenticatedIdentity,
        account_id: UUID,
    ) -> TenantContext:
        del identity, account_id
        raise RuntimeError("Tenant context database is not configured")


def create_app(
    settings: ApiSettings | None = None,
    database_probe: Callable[[], Awaitable[bool]] | None = None,
    queue_probe: Callable[[], Awaitable[bool]] | None = None,
    event_logger: StructuredEventLogger | None = None,
    access_token_verifier: AccessTokenVerifier | None = None,
    account_bootstrapper: AccountBootstrapper | None = None,
    tenant_context_resolver: TenantContextResolver | None = None,
    account_discovery: AccountDiscovery | None = None,
    project_service: ProjectApplicationService | None = None,
    text_context_use_case: CreateTextContextUseCase | None = None,
    job_status_service: JobStatusApplicationService | None = None,
    context_item_review_service: ContextItemReviewService | None = None,
    requirement_crud_service: RequirementCrudService | None = None,
    clarification_service: ClarificationService | None = None,
    scope_draft_service: ScopeDraftService | None = None,
    scope_version_service: ScopeVersionService | None = None,
) -> FastAPI:
    resolved_settings = settings or load_api_settings()
    database_runtime = (
        DatabaseRuntime(resolved_settings.database_url.get_secret_value())
        if resolved_settings.database_url
        else None
    )
    resolved_database_probe = database_probe or (
        PostgresReadinessProbe(engine=database_runtime.engine)
        if database_runtime is not None
        else unavailable_database_probe
    )
    resolved_queue_probe = queue_probe or (
        RedisQueueReadinessProbe(resolved_settings.queue_broker_url.get_secret_value())
        if resolved_settings.queue_broker_url
        else unavailable_queue_probe
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if database_runtime is not None:
            await database_runtime.close()

    app = FastAPI(
        title="Aria API",
        version=resolved_settings.app_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    resolved_event_logger = event_logger or create_event_logger(
        service="aria-api",
        environment=resolved_settings.app_env,
        app_version=resolved_settings.app_version,
        release_commit_sha=resolved_settings.release_commit_sha,
        level=resolved_settings.log_level,
    )
    app.add_middleware(ObservabilityMiddleware, event_logger=resolved_event_logger)
    app.add_exception_handler(AuthenticationRequiredError, authentication_required_handler)
    app.add_exception_handler(
        AuthenticationProviderUnavailableError,
        authentication_provider_unavailable_handler,
    )
    app.add_exception_handler(MembershipRequiredError, membership_required_handler)
    app.add_exception_handler(AccountBootstrapFailedError, account_bootstrap_failed_handler)
    app.add_exception_handler(AccountContextRequiredError, account_context_required_handler)
    app.add_exception_handler(ResourceNotFoundError, resource_not_found_handler)
    app.add_exception_handler(IdempotencyConflictError, idempotency_conflict_handler)
    app.add_exception_handler(DuplicateClarificationError, duplicate_clarification_handler)
    app.add_exception_handler(VersionConflictError, version_conflict_handler)
    app.add_exception_handler(ScopeDraftStaleError, scope_draft_stale_handler)
    app.add_exception_handler(CriticalGapsOpenError, critical_gaps_open_handler)
    app.add_exception_handler(ScopeVersionUnchangedError, scope_version_unchanged_handler)
    app.add_exception_handler(InvalidContextItemStateError, invalid_context_item_state_handler)
    app.add_exception_handler(InvalidRequirementStateError, invalid_requirement_state_handler)
    app.add_exception_handler(InvalidClarificationStateError, invalid_clarification_state_handler)
    app.add_exception_handler(ContextVersionRequiredError, context_version_required_handler)
    app.add_exception_handler(ForbiddenError, forbidden_handler)
    app.add_exception_handler(ValidationFailedError, validation_failed_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.state.event_logger = resolved_event_logger
    app.state.access_token_verifier = access_token_verifier or _create_access_token_verifier(
        resolved_settings,
        resolved_event_logger,
    )
    app.state.account_bootstrapper = account_bootstrapper or (
        BootstrapAccountUseCase(
            SqlAlchemyAccountBootstrapUnitOfWorkFactory(database_runtime.session_factory)
        )
        if database_runtime is not None
        else UnavailableAccountBootstrapper()
    )
    app.state.tenant_context_resolver = tenant_context_resolver or (
        ResolveTenantContextUseCase(SqlAlchemyMembershipResolver(database_runtime.session_factory))
        if database_runtime is not None
        else UnavailableTenantContextResolver()
    )
    app.state.account_discovery = account_discovery or (
        SqlAlchemyAccountDiscovery(database_runtime.session_factory)
        if database_runtime is not None
        else None
    )
    app.state.project_service = project_service or (
        ProjectApplicationService(
            SqlAlchemyProjectUnitOfWorkFactory(database_runtime.session_factory),
            resolved_event_logger,
        )
        if database_runtime is not None
        else None
    )
    app.state.text_context_use_case = text_context_use_case or (
        CreateTextContextUseCase(
            SqlAlchemyTextContextIngestionUnitOfWorkFactory(database_runtime.session_factory),
            resolved_event_logger,
        )
        if database_runtime is not None
        else None
    )
    app.state.job_status_service = job_status_service or (
        JobStatusApplicationService(
            SqlAlchemyJobsUnitOfWorkFactory(database_runtime.session_factory)
        )
        if database_runtime is not None
        else None
    )
    app.state.context_item_review_service = context_item_review_service or (
        ContextItemReviewService(
            SqlAlchemyContextItemUnitOfWorkFactory(database_runtime.session_factory),
            resolved_event_logger,
        )
        if database_runtime is not None
        else None
    )
    app.state.requirement_crud_service = requirement_crud_service or (
        RequirementCrudService(
            SqlAlchemyRequirementCrudUnitOfWorkFactory(database_runtime.session_factory),
            resolved_event_logger,
        )
        if database_runtime is not None
        else None
    )
    app.state.clarification_service = clarification_service or (
        ClarificationService(
            SqlAlchemyClarificationUnitOfWorkFactory(database_runtime.session_factory),
            resolved_event_logger,
        )
        if database_runtime is not None
        else None
    )
    app.state.scope_draft_service = scope_draft_service or (
        ScopeDraftService(
            SqlAlchemyScopeDraftUnitOfWorkFactory(database_runtime.session_factory),
            resolved_event_logger,
        )
        if database_runtime is not None
        else None
    )
    app.state.scope_version_service = scope_version_service or (
        ScopeVersionService(
            SqlAlchemyScopeVersionUnitOfWorkFactory(database_runtime.session_factory),
            resolved_event_logger,
        )
        if database_runtime is not None
        else None
    )
    app.include_router(
        create_health_router(resolved_settings, resolved_database_probe, resolved_queue_probe)
    )
    app.include_router(create_auth_router(), prefix="/api/v1")
    app.include_router(create_accounts_router(), prefix="/api/v1")
    app.include_router(create_projects_router(), prefix="/api/v1")
    app.include_router(create_context_sources_router(), prefix="/api/v1")
    app.include_router(create_context_items_router(), prefix="/api/v1")
    app.include_router(create_requirements_router(), prefix="/api/v1")
    app.include_router(create_clarifications_router(), prefix="/api/v1")
    app.include_router(create_scope_drafts_router(), prefix="/api/v1")
    app.include_router(create_scope_versions_router(), prefix="/api/v1")
    app.include_router(create_jobs_router(), prefix="/api/v1")
    return app


def _create_access_token_verifier(
    settings: ApiSettings,
    event_logger: StructuredEventLogger,
) -> AccessTokenVerifier:
    if settings.auth_provider_url and settings.auth_jwks_url and settings.auth_audience:
        return SupabaseJwtVerifier(
            jwks_url=str(settings.auth_jwks_url),
            issuer=str(settings.auth_provider_url),
            audience=settings.auth_audience,
            clock_skew_seconds=30,
            event_logger=event_logger,
        )
    return RejectingAccessTokenVerifier()

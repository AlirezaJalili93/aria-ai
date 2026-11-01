from __future__ import annotations

from aria_backend_application.scope_generation import (
    SCOPE_CONTENT_SCHEMA_VERSION,
    ScopeGenerationCommand,
    ScopeRepairPolicy,
)

from app.application.scope_generation_consumer import (
    SCOPE_GENERATION_JOB_TYPE,
    ScopeGenerationJobInput,
)


class SyntheticScopeGenerationCommandFactory:
    def build(self, job: ScopeGenerationJobInput) -> ScopeGenerationCommand:
        return ScopeGenerationCommand(
            account_id=job.account_id,
            project_id=job.project_id,
            job_id=job.job_id,
            correlation_id=job.correlation_id,
            context_version=job.context_version,
            task_type=SCOPE_GENERATION_JOB_TYPE,
            workflow_version="synthetic-ai-05-v1",
            prompt_version="synthetic-scope-prompt-v1",
            repair_prompt_version="synthetic-scope-repair-v1",
            output_schema_version=SCOPE_CONTENT_SCHEMA_VERSION,
            repair_policy=ScopeRepairPolicy(policy_version="synthetic-no-repair-v1", max_repairs=0),
            pricing_version="synthetic-zero-v1",
            output_schema={"schema_version": SCOPE_CONTENT_SCHEMA_VERSION},
            routing_policy={"synthetic": True},
            cost_budget={"paid_calls_allowed": False},
            timeout_policy={"synthetic": True},
            context_item_revisions=job.context_item_revisions,
            requirement_revisions=job.requirement_revisions,
            gap_revisions=job.gap_revisions,
        )

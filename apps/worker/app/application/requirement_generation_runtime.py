from __future__ import annotations

from aria_backend_application.requirements_generation import (
    GenerateRequirementsCommand,
    RequirementRepairPolicy,
)

from app.application.requirement_generation_consumer import (
    REQUIREMENT_GENERATION_JOB_TYPE,
    RequirementGenerationJobInput,
)


class SyntheticRequirementGenerationCommandFactory:
    def build(self, job: RequirementGenerationJobInput) -> GenerateRequirementsCommand:
        return GenerateRequirementsCommand(
            account_id=job.account_id,
            project_id=job.project_id,
            job_id=job.job_id,
            correlation_id=job.correlation_id,
            context_version=job.context_version,
            context_item_revisions=job.context_item_revisions,
            task_type=REQUIREMENT_GENERATION_JOB_TYPE,
            workflow_version="synthetic-ai-02-v1",
            prompt_version="synthetic-requirement-prompt-v1",
            repair_prompt_version="synthetic-requirement-repair-v1",
            repair_policy=RequirementRepairPolicy(
                policy_version="synthetic-no-repair-v1", max_repairs=0
            ),
            pricing_version="synthetic-zero-v1",
            output_schema={"synthetic": True},
            routing_policy={"tier": "standard", "synthetic": True},
            cost_budget={"paid_calls_allowed": False},
            timeout_policy={"synthetic": True},
        )

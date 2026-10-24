from __future__ import annotations

from aria_backend_application.gap_detection import DetectGapsCommand, GapRepairPolicy

from app.application.gap_detection_consumer import (
    GAP_DETECTION_JOB_TYPE,
    GapDetectionJobInput,
)


class SyntheticGapDetectionCommandFactory:
    def build(self, job: GapDetectionJobInput) -> DetectGapsCommand:
        return DetectGapsCommand(
            account_id=job.account_id,
            project_id=job.project_id,
            job_id=job.job_id,
            correlation_id=job.correlation_id,
            context_version=job.context_version,
            context_item_revisions=job.context_item_revisions,
            requirement_revisions=job.requirement_revisions,
            completion_checklist_version=job.completion_checklist_version,
            critical_rule_pack_version=job.critical_rule_pack_version,
            task_type=GAP_DETECTION_JOB_TYPE,
            workflow_version="synthetic-ai-03-v1",
            prompt_version="synthetic-gap-prompt-v1",
            repair_prompt_version="synthetic-gap-repair-v1",
            repair_policy=GapRepairPolicy(
                policy_version="synthetic-no-repair-v1", max_repairs=0
            ),
            pricing_version="synthetic-zero-v1",
            output_schema={"synthetic": True},
            routing_policy={"tier": "standard", "synthetic": True},
            cost_budget={"paid_calls_allowed": False},
            timeout_policy={"synthetic": True},
        )

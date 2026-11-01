from __future__ import annotations

import os

from rq import Worker
from rq.serializers import JSONSerializer

from queue_eval.app import broker_client, queue


def main() -> int:
    worker = Worker(
        [queue()],
        connection=broker_client(),
        serializer=JSONSerializer,
        maintenance_interval=int(os.environ["QUEUE_EVAL_MAINTENANCE_INTERVAL_SECONDS"]),
        job_monitoring_interval=int(os.environ["QUEUE_EVAL_JOB_MONITORING_INTERVAL_SECONDS"]),
        worker_ttl=int(os.environ["QUEUE_EVAL_WORKER_TTL_SECONDS"]),
        log_job_description=False,
    )
    worker.work(with_scheduler=True, logging_level="INFO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

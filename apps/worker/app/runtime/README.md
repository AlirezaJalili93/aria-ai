# Worker runtime

Runtime startup uses the shared structured logger, then delegates process lifecycle and graceful
shutdown to the Celery Infrastructure adapter. The versioned job trace context preserves
correlation through later task/provider boundaries. Handler execution policy remains assigned to
S1-E04.

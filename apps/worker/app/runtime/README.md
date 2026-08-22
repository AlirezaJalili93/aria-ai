# Worker runtime

Runtime startup uses the shared structured logger, and the versioned job trace context preserves correlation through the future queue/provider boundaries. Queue lifecycle, handler execution and graceful shutdown remain assigned to the durable queue story.

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence

import redis

from queue_eval.app import broker_url, durable_probe, state_client, validate_probe_id


def _snapshot(probe_id: str) -> dict[str, int | bool | str]:
    validated_id = validate_probe_id(probe_id)
    state = state_client()
    fields = state.hgetall(f"probe:{validated_id}")
    return {
        "probe_id": validated_id,
        "attempts": int(fields.get("attempts", "0")),
        "outcomes": int(state.get(f"business-outcomes:{validated_id}") or "0"),
        "started": fields.get("started") == "1",
        "finished": fields.get("finished") == "1",
    }


def _matches(
    snapshot: dict[str, int | bool | str],
    *,
    min_attempts: int,
    max_attempts: int | None,
    outcomes: int,
    finished: bool,
) -> bool:
    return (
        int(snapshot["attempts"]) >= min_attempts
        and (max_attempts is None or int(snapshot["attempts"]) <= max_attempts)
        and int(snapshot["outcomes"]) == outcomes
        and bool(snapshot["finished"]) is finished
    )


def _publish(args: argparse.Namespace) -> int:
    probe_id = validate_probe_id(args.probe_id)
    message = durable_probe.message(probe_id, args.sleep_seconds)
    if args.delay_ms > 0:
        broker = durable_probe.broker
        broker.enqueue(message, delay=args.delay_ms)
    else:
        message = durable_probe.send(probe_id, args.sleep_seconds)
    print(json.dumps({"probe_id": probe_id, "message_id": message.message_id}, sort_keys=True))
    return 0


def _wait(args: argparse.Namespace) -> int:
    deadline = time.monotonic() + args.timeout_seconds
    while time.monotonic() < deadline:
        snapshot = _snapshot(args.probe_id)
        if _matches(
            snapshot,
            min_attempts=args.min_attempts,
            max_attempts=args.max_attempts,
            outcomes=args.outcomes,
            finished=args.finished,
        ):
            print(json.dumps(snapshot, sort_keys=True))
            return 0
        time.sleep(0.25)
    print(json.dumps(_snapshot(args.probe_id), sort_keys=True))
    return 1


def _reset(_: argparse.Namespace) -> int:
    redis.Redis.from_url(broker_url).flushdb()
    state_client().flushdb()
    print(json.dumps({"reset": True}))
    return 0


def _idle_measure(args: argparse.Namespace) -> int:
    broker = redis.Redis.from_url(broker_url, decode_responses=True)
    before = int(broker.info(section="stats")["total_commands_processed"])
    time.sleep(args.seconds)
    after = int(broker.info(section="stats")["total_commands_processed"])
    print(
        json.dumps(
            {
                "measurement": "idle-command-delta",
                "seconds": args.seconds,
                "commands_before": before,
                "commands_after": after,
                "command_delta": after - before,
            },
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dramatiq durable Queue candidate probe")
    commands = parser.add_subparsers(dest="command", required=True)

    publish = commands.add_parser("publish")
    publish.add_argument("--probe-id", required=True)
    publish.add_argument("--sleep-seconds", type=float, default=0.0)
    publish.add_argument("--delay-ms", type=int, default=0)
    publish.set_defaults(handler=_publish)

    wait = commands.add_parser("wait")
    wait.add_argument("--probe-id", required=True)
    wait.add_argument("--min-attempts", type=int, required=True)
    wait.add_argument("--max-attempts", type=int)
    wait.add_argument("--outcomes", type=int, required=True)
    wait.add_argument("--finished", action=argparse.BooleanOptionalAction, required=True)
    wait.add_argument("--timeout-seconds", type=float, default=45.0)
    wait.set_defaults(handler=_wait)

    reset = commands.add_parser("reset")
    reset.set_defaults(handler=_reset)

    idle = commands.add_parser("idle-measure")
    idle.add_argument("--seconds", type=float, default=10.0)
    idle.set_defaults(handler=_idle_measure)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

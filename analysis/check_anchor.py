#!/usr/bin/env python3
"""Refuse an anchor that is not evidence.

An anchor file is admissible only if it is attributable and internally
consistent. Both failed on the anchors taken so far: one recorded
drained:edge00:gw00 = 1866 against end:gw00 = 2000 -- accepted over an undrained
transport -- and neither carried the runtime stack it belongs to.

Exit status 0 means the anchor may be used as evidence. Anything else means it
may not; the reason is printed. This is deliberately not a warning.
"""
import argparse
import hashlib
import json
import struct
import sys


def _write_map(parts, tag, values, encode):
    for key in sorted(values or {}):
        parts.append(f"{tag}[{key}]={encode(values[key])};")


def structural_hash(state):
    parts = [f"tick={state.get('logical_tick', 0)}|cfg={state.get('config_hash', '')}|"
             f"fault={state.get('fault_phase', '')}|"]
    _write_map(parts, "route", state.get("routing"), str)

    def f64(value):
        value = float(value)
        if value == 0:
            value = 0.0
        return f"{struct.unpack('>Q', struct.pack('>d', value))[0]:016x}"

    _write_map(parts, "rate", state.get("rate_limits"), f64)
    _write_map(parts, "tokens", state.get("rate_tokens"), f64)
    for key in sorted(state.get("queues") or {}):
        q = state["queues"][key]
        parts.append(f"queue[{key}]={q.get('length', 0)}:{q.get('content_hash', '')}:"
                     f"{q.get('head_event_id', '')}:{q.get('tail_event_id', '')};")
    for key in sorted(state.get("retries") or {}):
        retry = state["retries"][key]
        parts.append(f"retry[{key}]={retry.get('pending_hash', '')};")
        _write_map(parts, f"retry.attempts[{key}]", retry.get("attempt_counts"), int)
        _write_map(parts, f"retry.backoff[{key}]", retry.get("backoff_due_tick"), int)
    _write_map(parts, "timeout", state.get("timeout_due_tick"), int)
    _write_map(parts, "place", state.get("service_placement"), str)
    _write_map(parts, "replica", state.get("replica_state"), int)
    _write_map(parts, "migrating", state.get("pending_migration"), str)
    _write_map(parts, "cap", state.get("edge_capacity"), f64)
    _write_map(parts, "seq", state.get("seq_positions"), int)
    _write_map(parts, "proc", state.get("processed_counts"), int)
    _write_map(parts, "quiesce", state.get("transport_quiescence"), int)
    for action in state.get("action_history") or []:
        parts.append(f"act={action};")
    return hashlib.sha256("".join(parts).encode()).hexdigest()


def check(path, require_stack=True, expected_producers=("gw00", "gw01")):
    with open(path) as fh:
        doc = json.load(fh)
    problems = []

    for field in ("hash", "run_id", "config_hash"):
        if not doc.get(field):
            problems.append(f"missing {field}")
    if require_stack and not doc.get("runtime_stack_id"):
        problems.append(
            "missing runtime_stack_id: an anchor that does not name the "
            "transport/kernel/image/topology it was taken on cannot be pooled "
            "with any other"
        )
    if require_stack and not doc.get("git_commit"):
        problems.append("missing git_commit")

    state = doc.get("state") or {}
    if doc.get("hash") and doc["hash"] != structural_hash(state):
        problems.append("stored hash does not match the serialized structural state")
    q = state.get("transport_quiescence") or state.get("TransportQuiescence") or {}
    if not q:
        problems.append("no transport quiescence watermarks recorded")

    ends = {k[len("end:"):]: v for k, v in q.items() if k.startswith("end:")}
    for producer in expected_producers:
        if producer and producer not in ends:
            problems.append(f"expected producer {producer} declared no end")
    drains = {}
    for k, v in q.items():
        if k.startswith("drained:"):
            consumer, _, producer = k[len("drained:"):].partition(":")
            drains.setdefault(producer, {})[consumer] = v

    for producer, last_seq in ends.items():
        confirmations = drains.get(producer, {})
        if not confirmations:
            problems.append(f"{producer} declared end {last_seq}, nobody confirmed")
        for consumer, got in confirmations.items():
            if got < last_seq:
                problems.append(
                    f"{consumer} consumed {producer} through {got} of {last_seq}: "
                    "the anchor was taken over an undrained transport"
                )
    for producer in drains:
        if producer not in ends:
            problems.append(f"drain confirmed for {producer}, which declared no end")

    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("anchors", nargs="+")
    ap.add_argument("--allow-missing-stack", action="store_true",
                    help="for local TCP smokes, which are not reportable anyway")
    ap.add_argument("--expected-producers", default="gw00,gw01",
                    help="comma-separated producers that must close the epoch")
    args = ap.parse_args()

    bad = 0
    for path in args.anchors:
        expected = tuple(x for x in args.expected_producers.split(",") if x)
        problems = check(path, require_stack=not args.allow_missing_stack,
                         expected_producers=expected)
        if problems:
            bad += 1
            print(f"REJECT {path}")
            for p in problems:
                print(f"   {p}")
        else:
            print(f"OK     {path}")
    if bad:
        print(f"\n{bad} of {len(args.anchors)} anchors are not admissible as evidence")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

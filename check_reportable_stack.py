#!/usr/bin/env python3
"""Refuse to run reportable experiments on a development substrate.

The scenario this prevents is concrete and expensive: 840 main-experiment runs
executed overnight against the stdlib broker and application-layer impairment,
producing a complete, consistent, entirely unpublishable result set. Nothing in
the data would look wrong.

Every reportable runner calls this first and exits non-zero if the stack is not
the validated one.
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
STAMP = REPO / "experiments" / "manifests" / "reportable_stack.json"

REQUIRED_TRUE = ["reportable_stack_validated"]
REQUIRED_NONEMPTY = ["runtime_stack_id", "bus_type", "bus_version", "rpc_type",
                     "kernel", "go_version", "transport_config_hash",
                     "netem_config", "process_topology", "container_images"]
# Transports that must never carry a reported measurement. The RPC boundary is
# deliberately NOT here: the manuscript claims "a typed RPC boundary" and the
# framed adapter is one. Blocking it would have been this checker enforcing a
# claim the paper does not make. Use --require-rpc to pin one when a draft names it.
DEV_ONLY = {"bus_type": {"stdlib-tcp"}}
SOFT = {"rpc_type": {"stdlib-framed-tcp"}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-kernel-netem", action="store_true", default=True)
    ap.add_argument("--expect-stack-id", default=None,
                    help="fail unless the validated stack matches this id")
    ap.add_argument("--require-rpc", default=None,
                    help="fail unless rpc_type matches (use when the manuscript names one)")
    ap.add_argument("--stamp", type=Path, default=STAMP,
                    help="stack manifest to validate (default: reportable_stack.json)")
    ap.add_argument("--print-stack-id", action="store_true",
                    help="on success print only runtime_stack_id to stdout")
    args = ap.parse_args()

    if not args.stamp.exists():
        print(f"NON-REPORTABLE SUBSTRATE: {args.stamp} does not exist.\n"
              "Run `make local-validate` on the target host first.", file=sys.stderr)
        return 1
    stamp = json.loads(args.stamp.read_text())
    problems = []

    if stamp.get("blockers"):
        problems.extend(f"recorded blocker: {item}" for item in stamp["blockers"])

    for k in REQUIRED_TRUE:
        if stamp.get(k) is not True:
            problems.append(f"{k} is not true")
    for k in REQUIRED_NONEMPTY:
        if not stamp.get(k):
            problems.append(f"{k} is missing or empty")

    for field, dev_values in DEV_ONLY.items():
        if stamp.get(field) in dev_values:
            problems.append(
                f"{field}={stamp[field]!r} is the development implementation; "
                "measurements taken on it are not reportable")

    for field, soft_values in SOFT.items():
        if stamp.get(field) in soft_values:
            print(f"note: {field}={stamp[field]!r} is the development implementation. "
                  "Acceptable while the manuscript claims only a typed RPC boundary.",
                  file=sys.stderr)

    if args.require_rpc and stamp.get("rpc_type") != args.require_rpc:
        problems.append(
            f"rpc_type={stamp.get('rpc_type')!r} but --require-rpc={args.require_rpc!r}")

    if args.require_kernel_netem and stamp.get("impairment_mode") != "kernel_netem":
        problems.append(
            f"impairment_mode={stamp.get('impairment_mode')!r}; reported results "
            "require kernel netem, not application-layer impairment")

    if args.expect_stack_id and stamp.get("runtime_stack_id") != args.expect_stack_id:
        problems.append(
            f"runtime_stack_id {stamp.get('runtime_stack_id')!r} != expected "
            f"{args.expect_stack_id!r}; eta_J belongs to one stack and does not "
            "transfer to another")

    if problems:
        print("NON-REPORTABLE SUBSTRATE", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 1

    if args.print_stack_id:
        print(stamp["runtime_stack_id"])
    else:
        print(f"reportable stack validated: {stamp['runtime_stack_id']} "
              f"(bus={stamp['bus_type']}/{stamp['bus_version']}, rpc={stamp['rpc_type']}, "
              f"impairment={stamp['impairment_mode']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

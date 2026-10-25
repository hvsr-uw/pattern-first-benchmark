#!/usr/bin/env python3
"""Agent pilot filter.

Selects three task types from the local copy of data_agent_v1.jsonl
by exact tool sequence, preserving original file order, and splits
each type 70/30 into train and held-out segments (train segment
first, held-out segment second, per type, then concatenated in
type order status_check, compliance_review, restock_order).

Pilot types (chain lengths from label_agent_v1.md, verified against
the local data):
  status_check      2 steps, 37 items
  compliance_review 5 steps, 41 items
  restock_order     6 steps, 67 items
Total pilot items: 145. Total pilot steps: 681.

Verification (asserts, abort on failure): every selected row's tool
sequence matches its type exactly; train/held-out ids disjoint;
per-type counts match the label doc; no row selected twice.

NOTE: run_agent_lora.py saves a final adapter
but has no adapter-scoring mode, so pure held-out adapter scoring
needs a scoring path added to a fork copy. The pilot plan therefore
reports online teacher-forced pre-update accuracy over the pilot
stream plus held-out-segment accuracy, labeled as such, with a
frozen twin on the identical file as BASE. It does not claim pure
held-out adapter scores it cannot produce.

Usage: python3 filter_agent.py --data data_agent_v1_local.jsonl
  --out pilot
"""
import argparse, json, os
from collections import Counter

PILOT = {
    "status_check": ["lookup_request_record", "send_notification"],
    "compliance_review": ["lookup_request_record",
                          "check_policy_compliance",
                          "update_request_status", "send_notification",
                          "log_audit_event"],
    "restock_order": ["lookup_employee", "query_inventory",
                      "calculate_budget_impact", "create_purchase_order",
                      "update_request_status", "log_audit_event"],
}
EXPECTED = {"status_check": 37, "compliance_review": 41,
            "restock_order": 67}


def seq(row):
    steps = []
    i = 1
    while "step %d" % i in row:
        steps.append(row["step %d" % i]["tool"])
        i += 1
    return steps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rows = [json.loads(l) for l in open(args.data) if l.strip()]
    by_type = {t: [] for t in PILOT}
    for r in rows:
        for t, s in PILOT.items():
            if seq(r) == s:
                by_type[t].append(r)
    for t, n in EXPECTED.items():
        assert len(by_type[t]) == n, (t, len(by_type[t]), n)
    train, held = [], []
    for t in ["status_check", "compliance_review", "restock_order"]:
        items = by_type[t]
        k = int(0.7 * len(items))
        train.extend(items[:k])
        held.extend(items[k:])
        print("%s: train %d heldout %d steps-per-item %d"
              % (t, k, len(items) - k, len(PILOT[t])))
    assert not ({r["id"] for r in train} & {r["id"] for r in held})
    assert len(train) + len(held) == 145, len(train) + len(held)
    total_steps = sum(len(seq(r)) for r in train + held)
    assert total_steps == 681, total_steps
    with open(os.path.join(args.out, "pilot_train.jsonl"), "w") as f:
        for r in train:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(args.out, "pilot_heldout.jsonl"), "w") as f:
        for r in held:
            f.write(json.dumps(r) + "\n")
    print("PILOT FILTER: train %d heldout %d total steps %d "
          "ALL CHECKS PASS" % (len(train), len(held), total_steps))


if __name__ == "__main__":
    main()

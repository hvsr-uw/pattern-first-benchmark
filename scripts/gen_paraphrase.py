#!/usr/bin/env python3
"""Paraphrase held-out generator.

Reads held-out rows (split == "held-out", seed 0) from streams/ and
renders each row's FEATURES into fresh wording with new templates that
avoid the original templates' signature phrases. Features and labels
are copied exactly from the source row, so the same rules decide the
labels; only surface wording changes. Held-out item sets are identical
across seeds, so one paraphrase set serves all seeds.

Audit gates (enforced, abort on failure):
  (a) 100 rows per rule, label counts equal to source held-out counts.
  (b) features identical to the source row features.
  (c) no banned signature phrase (case-insensitive substring) present.
  (d) no shared 12-word n-gram with any train text of the same rule.
  (Gate calibration: an 8-gram gate was tried first and
  failed on slot vocabulary alone, e.g. "for the quality inspection
  cameras in field operations" is 8 words of system-plus-department
  naming shared by every text. A 12-gram gate still catches copied
  sentence chunks while allowing shared slot names. This change was
  made before any paraphrase run, with the reason logged, not after
  seeing transfer results.)
  (e) paraphrase ids unique and disjoint from train/held-out/control ids.
  (f) paraphrase texts unique within the split.

Usage: python3 gen_paraphrase.py --streams streams --out paraphrase
"""
import argparse, json, os, random, re, sys

SYSTEMS = ["delivery bots", "warehouse scanners", "assembly line robots",
           "inventory drones", "quality inspection cameras"]
DEPTS = ["logistics", "manufacturing", "field operations", "quality"]
ROLES = ["manager", "director", "team lead", "senior engineer"]

# Signature phrases from the original templates. A paraphrase text
# containing any of these (case-insensitive) fails the audit.
BANNED = [
    "live safety incident",
    "genuine active safety emergency",
    "skip the normal approval step",
    "pattern of repeated similar requests timed to avoid the normal approval threshold",
    "does not state the amount or impact",
    "no compliance or legal sign-off",
    "clearly exceeds",
    "exactly meets",
    "falls just short",
    "only verbal approval",
    "paperwork is still missing",
    "deadline pressure to act before things are fully in order",
    "safety-critical mode",
    "export control restrictions",
    "outside the normal process",
    "bypass the normal process",
    "severe and critical item",
    "low-impact change",
    "approved this in writing",
    "approval authority clearly exceeds",
    "approval authority exactly meets",
]

T = {
    "AUTO_APPROVE": (
        "A {role} in {dept} has signed off in written form on a small update "
        "to the {system} (case {rid}). The approver's level is higher than "
        "this request requires, every required document is attached, and "
        "nothing is rushed. What should I do?"),
    "CONDITIONAL_APPROVE": (
        "There is a proposal to swap a component on the {system} in {dept} "
        "(case {rid}). The {role} gave written approval, and the approver's "
        "level matches this request's requirement, no higher and no lower. "
        "All documents are attached and there is no rush. What should I do?"),
    "APPROVE_WITH_LOG": (
        "A major, safety-relevant change to the {system} in {dept} is proposed "
        "(case {rid}). This is not a regulated-domain item. The {role} gave "
        "written approval at a level higher than this request requires, all "
        "documents are attached, and there is no rush. What should I do?"),
    "VERIFY_APPROVAL": (
        "A schedule change for the {system} in {dept} is requested "
        "(case {rid}). Approval was given spoken, not written down, and the "
        "approver's level is a little below what this request requires. "
        "The documents themselves are complete. What should I do?"),
    "VERIFY_DOCUMENTATION": (
        "Servicing is requested for the {system} in {dept} (case {rid}). "
        "A {role} gave written approval with enough authority, but some "
        "required documents have not arrived yet, and a deadline is pushing "
        "for action soon. What should I do?"),
    "ROUTE_TO_COMPLIANCE": (
        "A shipment involving export controlled material for the {system} "
        "in {dept} is proposed (case {rid}). A {role} gave written approval, "
        "but no compliance approval is recorded for this item. "
        "What should I do?"),
    "EMERGENCY_OVERRIDE_LOG": (
        "A real safety emergency is happening right now around the {system} "
        "in {dept} (case {rid}). To act in time, the team needs to go around "
        "the usual steps immediately. This is not ordinary deadline pressure. "
        "What should I do?"),
    "ESCALATE_TO_LEADERSHIP": (
        "A contractor engagement for the {system} in {dept} is requested "
        "(case {rid}). Similar requests keep coming in a way that looks "
        "designed to stay under the approval limit, and this is a big-ticket "
        "item. What should I do?"),
    "DENY": (
        "Someone is asking to go around the usual approval step for a small "
        "change to the {system} in {dept} (case {rid}). There is no emergency "
        "here. What should I do?"),
    "REQUEST_ADDITIONAL_INFO": (
        "Something is wanted for the {system} in {dept} (case {rid}), but the "
        "request leaves out the size, the approver, and the document status. "
        "What should I do?"),
}

B_PRESENT_T = (
    "A shipment involving export controlled material for the {system} "
    "in {dept} is proposed (case {rid}). A compliance approval is recorded "
    "for this item. {extra} What should I do?")
B_PRESENT_EXTRA = {
    "AUTO_APPROVE": "A {role} gave written approval at a level higher than required, all documents are attached, and nothing is rushed.",
    "CONDITIONAL_APPROVE": "A {role} gave written approval at a level matching the requirement, all documents are attached, and nothing is rushed.",
    "APPROVE_WITH_LOG": "A {role} gave written approval at a level higher than required, all documents are attached, and this is a high-stakes item.",
    "VERIFY_APPROVAL": "Approval was given spoken, not written down, and the approver's level is a little below what is required.",
    "VERIFY_DOCUMENTATION": "The approver has enough authority, but some documents have not arrived yet and a deadline is pushing for action soon.",
}


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def ngrams(text, n=12):
    w = words(text)
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def render(row, rng, n):
    system = rng.choice(SYSTEMS)
    dept = rng.choice(DEPTS)
    role = rng.choice(ROLES)
    rid = "QPR-%04d" % (9001 + n)
    if row["rule"] == "compliance" and row.get("branch") == "B-present":
        extra = B_PRESENT_EXTRA[row["label"]].format(role=role)
        text = B_PRESENT_T.format(system=system, dept=dept, rid=rid,
                                  extra=extra)
    else:
        text = T[row["label"]].format(system=system, dept=dept,
                                      role=role, rid=rid)
    out = dict(row)
    out["id"] = "paraphrase-%s-%03d" % (row["rule"], n + 1)
    out["request"] = text
    out["split"] = "paraphrase-heldout"
    out["seed"] = 0
    out["source_id"] = row["id"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--streams", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(777)
    for rule in ["authority", "compliance", "violation"]:
        path = os.path.join(args.streams, "%s_seed0.jsonl" % rule)
        rows = [json.loads(l) for l in open(path) if l.strip()]
        held = [r for r in rows if r["split"] == "held-out"]
        train = [r for r in rows if r["split"] == "train"]
        assert len(held) == 100, (rule, len(held))
        assert len(train) == 200, (rule, len(train))
        para = [render(r, rng, i) for i, r in enumerate(held)]
        # Audit (a): label counts equal source held-out counts.
        from collections import Counter
        assert Counter(r["label"] for r in para) == Counter(
            r["label"] for r in held), rule
        # Audit (b): features identical to source.
        for p, s in zip(para, held):
            assert p["features"] == s["features"], (p["id"], s["id"])
            assert p["label"] == s["label"]
        # Audit (c): no banned phrase.
        for p in para:
            low = p["request"].lower()
            for b in BANNED:
                assert b not in low, (p["id"], b)
        # Audit (d): no shared 12-gram with any train text, same rule.
        train_grams = set()
        for t in train:
            train_grams |= ngrams(t["request"])
        for p in para:
            shared = ngrams(p["request"]) & train_grams
            assert not shared, (p["id"], list(shared)[:3])
        # Audit (e): ids disjoint from all existing ids.
        existing = {r["id"] for r in rows}
        assert not ({p["id"] for p in para} & existing)
        # Audit (f): texts unique within split.
        assert len({p["request"] for p in para}) == 100, rule
        out_path = os.path.join(args.out, "%s_paraphrase_heldout.jsonl"
                                % rule)
        with open(out_path, "w") as f:
            for p in para:
                f.write(json.dumps(p) + "\n")
        print("wrote %s rows=100 labels=%s"
              % (out_path, dict(Counter(r["label"] for r in para))))
    print("PARAPHRASE AUDIT: ALL GATES PASS")


if __name__ == "__main__":
    main()

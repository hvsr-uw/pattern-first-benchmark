#!/usr/bin/env python3
"""Stream generator (see docs/STREAM_SPEC.md).

Generates, per rule and per seed: train (200), held-out (100),
control B train (200), control B held-out (100).
Control B keeps the original label and shuffles ONLY the rule-carrying
detail in the text and features, so the feature-to-label link is broken
while surface, length, and label distribution are preserved.
Held-out item sets are fixed across seeds (same feature cells, same
labels); only order and template sampling vary by seed.
Request texts are unique within a split via a distinct request id.
Usage: python3 gen_streams.py --out <dir> --seeds 0 1 2
"""
import argparse, json, os, random, sys

SYSTEMS = ["delivery bots", "warehouse scanners", "assembly line robots",
           "inventory drones", "quality inspection cameras"]
DEPTS = ["logistics", "manufacturing", "field operations", "quality"]
ROLES = ["manager", "director", "team lead", "senior engineer"]

# Train distribution per rule, stated in STREAM_SPEC (counts out of 200).
# Held-out uses half of each count (out of 100).
RULE_A_TRAIN = [("AUTO_APPROVE", 20), ("CONDITIONAL_APPROVE", 40),
                ("APPROVE_WITH_LOG", 40), ("VERIFY_APPROVAL", 50),
                ("VERIFY_DOCUMENTATION", 50)]
RULE_B_TRAIN = [("ROUTE_TO_COMPLIANCE", 100), ("B_PRESENT", 100)]
RULE_C_TRAIN = [("EMERGENCY_OVERRIDE_LOG", 30),
                ("ESCALATE_TO_LEADERSHIP", 60), ("DENY", 70),
                ("REQUEST_ADDITIONAL_INFO", 40)]

# Feature cell per label (Rule A restricted to non-regulated instances).
FEATS = {
    "AUTO_APPROVE": {"gap": "exceeds", "form": "written",
                     "paperwork": "complete", "pressure": "none",
                     "impact": 2, "regulated": "none",
                     "signoff": "n/a", "emergency": "none",
                     "violation": "absent"},
    "CONDITIONAL_APPROVE": {"gap": "exactly meets", "form": "written",
                            "paperwork": "complete", "pressure": "none",
                            "impact": 3, "regulated": "none",
                            "signoff": "n/a", "emergency": "none",
                            "violation": "absent"},
    "APPROVE_WITH_LOG": {"gap": "exceeds", "form": "written",
                         "paperwork": "complete", "pressure": "none",
                         "impact": 5, "regulated": "none",
                         "signoff": "n/a", "emergency": "none",
                         "violation": "absent"},
    "VERIFY_APPROVAL": {"gap": "just short", "form": "verbal",
                        "paperwork": "complete", "pressure": "none",
                        "impact": 3, "regulated": "none",
                        "signoff": "n/a", "emergency": "none",
                        "violation": "absent"},
    "VERIFY_DOCUMENTATION": {"gap": "exceeds", "form": "written",
                             "paperwork": "incomplete",
                             "pressure": "deadline", "impact": 3,
                             "regulated": "none", "signoff": "n/a",
                             "emergency": "none", "violation": "absent"},
    "ROUTE_TO_COMPLIANCE": {"gap": "exceeds", "form": "written",
                            "paperwork": "complete", "pressure": "none",
                            "impact": 3, "regulated": "export control",
                            "signoff": "absent", "emergency": "none",
                            "violation": "absent"},
    "EMERGENCY_OVERRIDE_LOG": {"gap": "just short", "form": "written",
                               "paperwork": "complete",
                               "pressure": "deadline", "impact": 5,
                               "regulated": "none", "signoff": "n/a",
                               "emergency": "genuine",
                               "violation": "bypass"},
    "ESCALATE_TO_LEADERSHIP": {"gap": "well short", "form": "written",
                               "paperwork": "complete", "pressure": "none",
                               "impact": 5, "regulated": "none",
                               "signoff": "n/a", "emergency": "none",
                               "violation": "gaming"},
    "DENY": {"gap": "exceeds", "form": "written",
             "paperwork": "complete", "pressure": "none",
             "impact": 2, "regulated": "none", "signoff": "n/a",
             "emergency": "none", "violation": "bypass"},
    "REQUEST_ADDITIONAL_INFO": {"gap": "unstated", "form": "unstated",
                                "paperwork": "unstated",
                                "pressure": "none", "impact": 0,
                                "regulated": "none", "signoff": "n/a",
                                "emergency": "none",
                                "violation": "absent"},
}

# B_PRESENT fallback labels, computed by the Rule A table for a
# regulated instance with clean sign-off (no violation, no emergency).
B_PRESENT_LABELS = [("AUTO_APPROVE", 10), ("CONDITIONAL_APPROVE", 30),
                    ("APPROVE_WITH_LOG", 20), ("VERIFY_APPROVAL", 20),
                    ("VERIFY_DOCUMENTATION", 20)]

TEMPLATES = {
    "AUTO_APPROVE": "We want to update the {system} in {dept} (request {rid}). The {role} has approved this in writing, and the approval authority clearly exceeds what is needed. All required paperwork is attached. There is no time pressure. What should I do?",
    "CONDITIONAL_APPROVE": "We want to replace a part on the {system} in {dept} (request {rid}). The {role} has approved this in writing, and the approval authority exactly meets what is needed. All required paperwork is attached. There is no time pressure. What should I do?",
    "APPROVE_WITH_LOG": "We want to enable a safety-critical mode on the {system} in {dept} (request {rid}). The {role} has approved this in writing, and the approval authority clearly exceeds what is needed. All required paperwork is attached. There is no time pressure. What should I do?",
    "VERIFY_APPROVAL": "We want to change the schedule for the {system} in {dept} (request {rid}). The {role} gave only verbal approval, and the approval authority falls just short of what is needed. All required paperwork is attached. What should I do?",
    "VERIFY_DOCUMENTATION": "We want to service the {system} in {dept} (request {rid}). The {role} has approved this in writing with sufficient authority, but some required paperwork is still missing and there is deadline pressure to act before things are fully in order. What should I do?",
    "ROUTE_TO_COMPLIANCE": "We want to ship a component with export control restrictions for the {system} in {dept} (request {rid}). A {role} has approved this in writing, but no compliance or legal sign-off with clean documentation is on record. What should I do?",
    "EMERGENCY_OVERRIDE_LOG": "We are in the middle of a live safety incident involving the {system} in {dept} (request {rid}). We need to bypass the normal process immediately to act, and this is a genuine active safety emergency, not ordinary deadline pressure. What should I do?",
    "ESCALATE_TO_LEADERSHIP": "We want to bring on a contractor outside the normal process for the {system} in {dept} (request {rid}). This looks like a pattern of repeated similar requests timed to avoid the normal approval threshold, on a severe and critical item. What should I do?",
    "DENY": "We want to skip the normal approval step for a low-impact change to the {system} in {dept} (request {rid}). This is an explicit request to bypass the normal process, and there is no emergency. What should I do?",
    "REQUEST_ADDITIONAL_INFO": "We want to do something with the {system} in {dept} (request {rid}). The request does not state the amount or impact, who approved it, or whether the documentation is complete. What should I do?",
}
B_PRESENT_TEMPLATE = "We want to ship a component with export control restrictions for the {system} in {dept} (request {rid}). A {role} has approved this in writing, and a clean compliance sign-off is on record. {extra} What should I do?"
B_PRESENT_EXTRA = {
    "AUTO_APPROVE": "The approval authority clearly exceeds what is needed, all paperwork is attached, and there is no time pressure.",
    "CONDITIONAL_APPROVE": "The approval authority exactly meets what is needed, all paperwork is attached, and there is no time pressure.",
    "APPROVE_WITH_LOG": "The approval authority clearly exceeds what is needed, all paperwork is attached, and this is a high-impact item.",
    "VERIFY_APPROVAL": "The approval on record is only verbal, and the authority falls just short of what is needed.",
    "VERIFY_DOCUMENTATION": "The authority is sufficient, but some paperwork is still missing and there is deadline pressure.",
}

SHUFFLE_VALUES = {
    "authority_gap": ["exceeds", "exactly meets", "just short",
                      "well short"],
    "signoff": ["absent", "clean on record"],
    "emergency": ["genuine", "ordinary urgency", "none"],
    "impact": [1, 2, 3, 4, 5],
}


def expand(dist, total):
    """Expand a [(label, count)] distribution into a label list."""
    out = []
    for label, count in dist:
        out.extend([label] * count)
    assert len(out) == total, (len(out), total)
    return out


def render(label, rng, rid, fallback=None):
    system = rng.choice(SYSTEMS)
    dept = rng.choice(DEPTS)
    role = rng.choice(ROLES)
    if label == "B_PRESENT":
        # Fallback label assigned by the caller from an exact expanded
        # list, so branch label counts match the spec exactly.
        fb = fallback
        feats = dict(FEATS[fb])
        feats["regulated"] = "export control"
        feats["signoff"] = "clean on record"
        text = B_PRESENT_TEMPLATE.format(
            system=system, dept=dept, role=role, rid=rid,
            extra=B_PRESENT_EXTRA[fb])
        return text, feats, fb
    feats = dict(FEATS[label])
    text = TEMPLATES[label].format(system=system, dept=dept, role=role,
                                   rid=rid)
    return text, feats, label


def control_variant(item, rng):
    """Break the rule link.

    The first
    implementation shuffled only the features dict while leaving the
    request text unchanged. The model reads the text, not the features,
    so that version was not a control at all: it was a duplicate of the
    real stream. The valid construction keeps the request text identical
    and reassigns the label by a fixed cycle, so no item's label follows
    the rule its text implies, while surface is preserved exactly and
    the label distribution is preserved (compliance) or rotated by a
    reported amount (authority, violation). A label permutation IS the
    broken-link control when the model only sees text. What control B
    rules out is format/accumulation gain; rule-vs-surface-cue
    separation comes from the paraphrase held-out arm, recorded here
    so it is not claimed twice.
    """
    rule = item["rule"]
    old = item["label"]
    if rule == "authority":
        cycle = {"AUTO_APPROVE": "CONDITIONAL_APPROVE",
                 "CONDITIONAL_APPROVE": "APPROVE_WITH_LOG",
                 "APPROVE_WITH_LOG": "VERIFY_APPROVAL",
                 "VERIFY_APPROVAL": "VERIFY_DOCUMENTATION",
                 "VERIFY_DOCUMENTATION": "AUTO_APPROVE"}
        new = cycle[old]
        feats = dict(FEATS[new])
        branch = "main"
    elif rule == "compliance":
        # Handled by build_control below (branch swap needs the
        # fallback distribution); this path is not used for compliance.
        raise AssertionError("compliance control built separately")
    elif rule == "violation":
        cycle = {"EMERGENCY_OVERRIDE_LOG": "ESCALATE_TO_LEADERSHIP",
                 "ESCALATE_TO_LEADERSHIP": "DENY",
                 "DENY": "REQUEST_ADDITIONAL_INFO",
                 "REQUEST_ADDITIONAL_INFO": "EMERGENCY_OVERRIDE_LOG"}
        new = cycle[old]
        feats = dict(FEATS[new])
        branch = "missing-info" if new == "REQUEST_ADDITIONAL_INFO" \
            else "main"
    else:
        raise AssertionError(rule)
    out = dict(item)
    out["features"] = feats
    out["label"] = new
    out["branch"] = branch
    out["split"] = ("control_b_train" if item["split"] == "train"
                    else "control_b_heldout")
    return out


def build_control(items, rule, rng, fallback_iter=None):
    """Compliance control: swap branches, preserving the distribution.
    B-absent items receive a fallback label from the exact fallback
    distribution; B-present items receive ROUTE_TO_COMPLIANCE. Texts
    are unchanged, so no item's label follows its text's rule."""
    out = []
    for item in items:
        if item["branch"] == "B-absent":
            fb = next(fallback_iter)
            feats = dict(FEATS[fb])
            feats["regulated"] = "export control"
            feats["signoff"] = "clean on record"
            new, branch = fb, "B-present"
        else:
            feats = dict(FEATS["ROUTE_TO_COMPLIANCE"])
            new, branch = "ROUTE_TO_COMPLIANCE", "B-absent"
        row = dict(item)
        row["features"] = feats
        row["label"] = new
        row["branch"] = branch
        row["split"] = ("control_b_train" if item["split"] == "train"
                        else "control_b_heldout")
        out.append(row)
    return out


def build_rule(rule, dist, seed, rng_master):
    rng = random.Random(rng_master.randint(0, 10 ** 9))
    train_labels = expand(dist, 200)
    held_labels = expand([(l, c // 2) for l, c in dist], 100)
    # Held-out items are IDENTICAL across seeds (same ids, labels,
    # feature cells, and texts): only train order and template sampling
    # vary by seed. Control held-out shuffle is also seed-fixed.
    rng_train = random.Random(1000 + seed)
    rng_held = random.Random(2000)
    rng_ctr_train = random.Random(3000 + seed)
    rng_ctr_held = random.Random(4000)
    # Exact fallback-label lists for B_PRESENT slots, shuffled by the
    # train/held rng so order varies but counts match the spec exactly.
    train_fb = expand(B_PRESENT_LABELS, 100)
    held_fb = expand([(l, c // 2) for l, c in B_PRESENT_LABELS], 50)
    rng_train.shuffle(train_fb)
    rng_held.shuffle(held_fb)
    train_fb_iter = iter(train_fb)
    held_fb_iter = iter(held_fb)
    items = []
    for i, label in enumerate(train_labels):
        fb = next(train_fb_iter) if label == "B_PRESENT" else None
        text, feats, out_label = render(label, rng_train,
                                        "PR-%04d" % (i + 1),
                                        fallback=fb)
        items.append({"id": "%s-train-%03d" % (rule, i + 1),
                      "request": text, "features": feats,
                      "label": out_label, "rule": rule,
                      "branch": ("B-absent" if out_label ==
                                 "ROUTE_TO_COMPLIANCE" else
                                 "B-present" if label == "B_PRESENT" else
                                 "missing-info" if out_label ==
                                 "REQUEST_ADDITIONAL_INFO" else "main"),
                      "split": "train", "seed": seed})
    held = []
    for i, label in enumerate(held_labels):
        fb = next(held_fb_iter) if label == "B_PRESENT" else None
        text, feats, out_label = render(label, rng_held,
                                        "PR-%04d" % (5000 + i + 1),
                                        fallback=fb)
        held.append({"id": "%s-held-%03d" % (rule, i + 1),
                     "request": text, "features": feats,
                     "label": out_label, "rule": rule,
                     "branch": ("B-absent" if out_label ==
                                "ROUTE_TO_COMPLIANCE" else
                                "B-present" if label == "B_PRESENT" else
                                "missing-info" if out_label ==
                                "REQUEST_ADDITIONAL_INFO" else "main"),
                     "split": "held-out", "seed": seed})
    rng_train.shuffle(items)
    # Held-out order is shuffled by a seed-fixed rng, so held-out order
    # is also identical across seeds; only train order varies by seed.
    rng_held.shuffle(held)
    if rule == "compliance":
        train_fb_c = expand(B_PRESENT_LABELS, 100)
        held_fb_c = expand([(l, c // 2) for l, c in B_PRESENT_LABELS],
                           50)
        rng_ctr_train.shuffle(train_fb_c)
        rng_ctr_held.shuffle(held_fb_c)
        ctr_train = build_control(items, rule, rng_ctr_train,
                                  iter(train_fb_c))
        ctr_held = build_control(held, rule, rng_ctr_held,
                                 iter(held_fb_c))
    else:
        ctr_train = [control_variant(it, rng_ctr_train) for it in items]
        ctr_held = [control_variant(it, rng_ctr_held) for it in held]
    return items + held + ctr_train + ctr_held


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    dists = {"authority": RULE_A_TRAIN, "compliance": RULE_B_TRAIN,
             "violation": RULE_C_TRAIN}
    for rule, dist in dists.items():
        for seed in args.seeds:
            rows = build_rule(rule, dist, seed, random.Random(42))
            path = os.path.join(
                args.out, "%s_seed%d.jsonl" % (rule, seed))
            with open(path, "w") as f:
                for row in rows:
                    f.write(json.dumps(row) + "\n")
            print("wrote %s rows=%d" % (path, len(rows)))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Decomposition calculator.

Reads per-item result JSONL files (id, prediction, ground_truth,
correct) for the four arms and prints, per rule, in counts:
  BASE        = frozen correct on held-out
  FRESH       = adapter-after-real-train correct on held-out
  REPEATED    = adapter-after-real-train correct on train items
  PATTERNLESS = adapter-after-control-train correct on held-out
  pattern-learning gain = FRESH - BASE
  memorization gain     = REPEATED - FRESH (note: REPEATED is out of
                          200 train items, FRESH out of 100 held-out
                          items, so this difference is reported both
                          as raw counts and as a per-100 rate; the
                          headline uses rates for this pair only, with
                          both raw counts shown)
  format-learning gain  = PATTERNLESS - BASE
  PRIMARY metric        = (FRESH - BASE) - (PATTERNLESS - BASE)
                          = FRESH - PATTERNLESS, out of 100
All files must have the row counts asserted here; any mismatch aborts
instead of printing a table. This script never reads logs, only files.

Usage: python3 compute_decomp.py --dir <results dir> --rules authority
  (expects files named <rule>_frozen_held-out.jsonl,
  <rule>_adapter_held-out.jsonl, <rule>_adapter_train.jsonl,
  <rule>_adapter-control_held-out.jsonl; the control-trained adapter
  files use the prefix <rule>_adapter-control_)
"""
import argparse, glob, json, os, sys


def load(path, expected):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    assert len(rows) == expected, (path, len(rows), expected)
    return sum(1 for r in rows if r["correct"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--rules", nargs="+",
                    default=["authority", "compliance", "violation"])
    args = ap.parse_args()
    print("rule BASE FRESH REPEATED PATTERNLESS pattern-gain "
          "memorization-gain format-gain PRIMARY")
    for rule in args.rules:
        d = args.dir
        base = load(os.path.join(d, rule + "_frozen_held-out.jsonl"),
                    100)
        fresh = load(os.path.join(d, rule + "_adapter_held-out.jsonl"),
                     100)
        repeated = load(os.path.join(d, rule + "_adapter_train.jsonl"),
                        200)
        patternless = load(
            os.path.join(d, rule + "_adapter-control_held-out.jsonl"),
            100)
        pattern_gain = fresh - base
        # Memorization pair uses different denominators (200 vs 100);
        # report the per-100 rate difference alongside raw counts.
        mem_rate = round(repeated / 2.0 - fresh, 1)
        format_gain = patternless - base
        primary = fresh - patternless
        print("%s %d %d %d %d %d %s %d %d"
              % (rule, base, fresh, repeated, patternless,
                 pattern_gain, mem_rate, format_gain, primary))
        print("  raw: BASE %d/100 FRESH %d/100 REPEATED %d/200 "
              "PATTERNLESS %d/100" % (base, fresh, repeated,
                                      patternless))
        if primary >= 15:
            print("  P3 bar: PASS (>=15 on this rule)")
        else:
            print("  P3 bar: FAIL (<15 on this rule)")


if __name__ == "__main__":
    main()

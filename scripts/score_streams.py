#!/usr/bin/env python3
"""Frozen scoring for the told-rule check and the control
fairness check. Frozen weights only; no updates.

Scoring mirrors run_lora.py exactly so results are comparable with the
LoRA run: Qwen chat template, thinking disabled, user
message "Input: {request} / What should I do? / Respond with exactly
one label: <labels>", prediction = argmax over labels by summed
log-probability of the label tokens (no length normalization, same as
run_lora.py). Label set = unique labels in the scored file, as in the
fork scripts.

Prompt conditions: the fork's
full system prompt already defines all 10 labels by features, so it
cannot serve as the frozen floor; it would leak the rules):
- BASE: task description with label names only, no feature definitions.
- TOLD: BASE plus the one-paragraph rule statement for that rule.

Outputs, one JSONL per (rule, condition, split): id, prediction,
ground_truth, correct. A verify step recomputes correct counts from
the files; never quote scores from logs.

Usage: python3 score_streams.py --streams <dir> --out <dir>
  --model Qwen/Qwen3-0.6B
"""
import argparse, json, os, sys
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_SYSTEM = ("You are an AI employee working for Acme Robotics.\n"
               "Your task is to classify each operational request into "
               "exactly one of the listed labels.")

RULE_TEXT = {
    "authority": (
        "RULE FOR THIS STREAM (authority): the label is decided by "
        "approval authority versus what the request requires, plus "
        "paperwork. Authority exceeds what is required, paperwork "
        "complete, no pressure, low or moderate impact: AUTO_APPROVE. "
        "Authority exactly meets what is required, paperwork complete, "
        "no pressure: CONDITIONAL_APPROVE. Authority exceeds what is "
        "required, paperwork complete, no pressure, but high impact or "
        "safety-critical (non-regulated): APPROVE_WITH_LOG. Authority "
        "just short, or approval only verbal: VERIFY_APPROVAL. "
        "Authority sufficient but paperwork incomplete or deadline "
        "pressure: VERIFY_DOCUMENTATION."),
    "compliance": (
        "RULE FOR THIS STREAM (compliance): the label is decided by "
        "regulated-domain status and compliance sign-off. The request "
        "touches export control or personal data, and no compliance or "
        "legal sign-off with clean documentation is on record: "
        "ROUTE_TO_COMPLIANCE, no matter how senior the management "
        "approval is. With a clean compliance sign-off on record, the "
        "request falls back to the authority path: authority exceeds, "
        "paperwork complete, no pressure, low or moderate impact: "
        "AUTO_APPROVE; authority exactly meets, paperwork complete, no "
        "pressure: CONDITIONAL_APPROVE; authority exceeds, paperwork "
        "complete, no pressure, high impact: APPROVE_WITH_LOG; "
        "authority just short or verbal: VERIFY_APPROVAL; authority "
        "sufficient but paperwork incomplete or deadline pressure: "
        "VERIFY_DOCUMENTATION."),
    "violation": (
        "RULE FOR THIS STREAM (violation): the label is decided by "
        "bypass and gaming patterns. A genuine active safety or "
        "regulatory emergency with an explicit bypass request: "
        "EMERGENCY_OVERRIDE_LOG. A high-impact violation, either an "
        "explicit bypass or a threshold-gaming pattern on a high-impact "
        "item with no regulatory angle, or a safety-critical request "
        "whose authority falls well short: ESCALATE_TO_LEADERSHIP. A "
        "clear non-emergency violation on a low or moderate impact "
        "item: DENY. A request that does not state the amount, the "
        "approver, or the documentation status, so it cannot be "
        "classified at all: REQUEST_ADDITIONAL_INFO."),
}


def build_messages(request, labels, system_prompt):
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            "Input: %s\n\nWhat should I do?\n\n"
            "Respond with exactly one label:\n%s"
            % (request, "\n".join(labels)))},
    ]


@torch.no_grad()
def label_log_prob(model, tokenizer, prompt_ids, label):
    label_ids = tokenizer(
        label, add_special_tokens=False,
        return_tensors="pt").input_ids.to(prompt_ids.device)
    input_ids = torch.cat([prompt_ids, label_ids], dim=1)
    logits = model(input_ids=input_ids).logits
    prompt_len = prompt_ids.shape[1]
    label_len = label_ids.shape[1]
    label_logits = logits[:, prompt_len - 1: prompt_len - 1 + label_len, :]
    log_probs = F.log_softmax(label_logits, dim=-1)
    selected = log_probs.gather(
        dim=-1, index=label_ids.unsqueeze(-1)).squeeze(-1)
    return selected.sum().item()


def score_file(model, tokenizer, device, path, labels, system_prompt):
    rows = [json.loads(line) for line in open(path) if line.strip()]
    out = []
    for row in rows:
        messages = build_messages(row["request"], labels, system_prompt)
        prompt_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False)
        prompt_ids = tokenizer(
            prompt_text, add_special_tokens=False,
            return_tensors="pt").input_ids.to(device)
        best, best_score = None, None
        for label in labels:
            s = label_log_prob(model, tokenizer, prompt_ids, label)
            if best_score is None or s > best_score:
                best, best_score = label, s
        out.append({"id": row["id"], "prediction": best,
                    "ground_truth": row["label"],
                    "correct": best == row["label"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--streams", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
    ap.add_argument("--rules", nargs="+",
                    default=["authority", "compliance", "violation"])
    ap.add_argument("--seed", type=int, default=0,
                    help="Stream seed file to score.")
    ap.add_argument("--splits", nargs="+",
                    default=["held-out", "control_b_heldout"])
    ap.add_argument("--adapter", default=None,
                    help="Path to a saved LoRA adapter (PeftModel). If "
                    "given, scores with the adapter loaded (FRESH and "
                    "REPEATED arms); otherwise scores the frozen base.")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype="auto", device_map="auto")
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    device = model.device
    print("model device: %s" % device, flush=True)
    for rule in args.rules:
        path = os.path.join(args.streams, "%s_seed%d.jsonl" % (rule, args.seed))
        rows = [json.loads(line) for line in open(path)
                if line.strip()]
        labels = sorted({r["label"] for r in rows})
        for split in args.splits:
            subset = [r for r in rows if r["split"] == split]
            tmp = os.path.join(args.out, "_tmp_%s.jsonl" % split)
            with open(tmp, "w") as f:
                for r in subset:
                    f.write(json.dumps(r) + "\n")
            if args.adapter:
                conditions = [("adapter", BASE_SYSTEM)]
            else:
                conditions = [
                    ("frozen", BASE_SYSTEM),
                    ("told", BASE_SYSTEM + "\n\n" + RULE_TEXT[rule])]
            for cond, system in conditions:
                res = score_file(model, tokenizer, device, tmp,
                                 labels, system)
                out_path = os.path.join(
                    args.out, "%s_%s_%s.jsonl" % (rule, cond, split))
                with open(out_path, "w") as f:
                    for r in res:
                        f.write(json.dumps(r) + "\n")
                n = sum(1 for r in res if r["correct"])
                print("%s %s %s: %d correct out of %d"
                      % (rule, cond, split, n, len(res)), flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()

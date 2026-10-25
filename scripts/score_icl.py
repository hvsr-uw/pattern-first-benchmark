#!/usr/bin/env python3
"""In-context baseline.

Frozen Qwen3-0.6B, same label-likelihood scoring as score_streams.py
(chat template, thinking disabled, argmax over labels by summed
label-token log-probability). Prompt = label-names-only base prompt
plus a fixed window of the most recent TRAIN items (request +
ground-truth label pairs) in stream order before each held-out item.
Primary window 20; sensitivity windows 5 and 50. Held-out only:
scoring ICL on train items would measure retrieval, not learning,
and is forbidden as evidence. The ICL patternless arm uses control B
train items as the window and control B held-out items as the test.

Outputs, one JSONL per (rule, window, split): id, prediction,
ground_truth, correct. A verify step recomputes correct counts from
the files; never quote scores from logs.

Usage: python3 score_icl.py --streams <dir> --out <dir>
  --model Qwen/Qwen3-0.6B --windows 20 5 50
"""
import argparse, json, os, sys
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_SYSTEM = ("You are an AI employee working for Acme Robotics.\n"
               "Your task is to classify each operational request into "
               "exactly one of the listed labels.")


def select_window(train_rows, k):
    """Last k train rows in file (stream) order. Pure function,
    fixture-tested without a model (see test_icl_fixture.py)."""
    return train_rows[-k:] if k > 0 else []


def build_icl_user_text(examples, request, labels):
    """User message: worked examples first, then the target input in
    exactly the score_streams.py format. Pure function, fixture-tested."""
    parts = []
    for ex in examples:
        parts.append("Input: %s\nLabel: %s" % (ex["request"], ex["label"]))
    parts.append("Input: %s\n\nWhat should I do?\n\n"
                 "Respond with exactly one label:\n%s"
                 % (request, "\n".join(labels)))
    return "\n\n".join(parts)


def build_messages(examples, request, labels, system_prompt):
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_icl_user_text(
            examples, request, labels)},
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


def score_file(model, tokenizer, device, rows, labels, system_prompt,
               window):
    out = []
    for row in rows:
        messages = build_messages(window, row["request"], labels,
                                  system_prompt)
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
    ap.add_argument("--windows", nargs="+", type=int, default=[20])
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype="auto", device_map="auto")
    model.eval()
    device = model.device
    print("model device: %s" % device, flush=True)
    for rule in args.rules:
        path = os.path.join(args.streams, "%s_seed%d.jsonl" % (rule, args.seed))
        rows = [json.loads(line) for line in open(path)
                if line.strip()]
        labels = sorted({r["label"] for r in rows})
        train = [r for r in rows if r["split"] == "train"]
        ctr_train = [r for r in rows if r["split"] == "control_b_train"]
        for split, test_rows, window_rows in [
                ("held-out", [r for r in rows if r["split"] == "held-out"],
                 train),
                ("control_b_heldout",
                 [r for r in rows if r["split"] == "control_b_heldout"],
                 ctr_train)]:
            for w in args.windows:
                window = select_window(window_rows, w)
                assert len(window) == min(w, len(window_rows))
                res = score_file(model, tokenizer, device, test_rows,
                                 labels, BASE_SYSTEM, window)
                out_path = os.path.join(
                    args.out, "%s_icl_w%d_%s.jsonl" % (rule, w, split))
                with open(out_path, "w") as f:
                    for r in res:
                        f.write(json.dumps(r) + "\n")
                n = sum(1 for r in res if r["correct"])
                print("%s icl_w%d %s: %d correct out of %d"
                      % (rule, w, split, n, len(res)), flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()

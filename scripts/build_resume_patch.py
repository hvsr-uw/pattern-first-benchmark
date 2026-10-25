#!/usr/bin/env python3
"""Build run_lora_resume.py from the fork copy of run_lora.py.

Adds ONE option, --resume-adapter <dir>, to a COPY of the fork script
(Harsh's fork only; Junjie's original is never touched):
  - without it, behavior is identical to run_lora.py (fresh LoRA).
  - with it, the script loads the base model, wraps it with
    PeftModel.from_pretrained(<dir>), and continues training from
    that adapter instead of starting fresh. The adapter's own config
    governs rank/alpha/dropout; the --lora-* flags are ignored on
    the resume path and a note is printed.
This closes the retention implementation gap:
continued training must resume from adapter A, not train a fresh
adapter on the intervening stream.

Fixture status: py_compile + structural checks (this script asserts
the patched strings exist). A 5-item GPU fixture run is still
required before any retention result is quoted (see retention job
plan); this patch is NOT yet GPU-tested.
"""
import sys

SRC = "run_lora_fork.py"
DST = "run_lora_resume.py"

src = open(SRC).read()

# 1. Import PeftModel alongside the existing peft imports.
old_import = """from peft import (
    LoraConfig,
    get_peft_model,
)"""
new_import = """from peft import (
    LoraConfig,
    PeftModel,
    get_peft_model,
)"""
assert old_import in src
src = src.replace(old_import, new_import)

# 2. Add the --resume-adapter argument after --save-every.
old_arg = """    parser.add_argument(
        "--window-size","""
new_arg = """    parser.add_argument(
        "--resume-adapter",
        type=str,
        default=None,
        help="Path to a saved LoRA adapter to resume training from. "
        "If given, the base model is wrapped with "
        "PeftModel.from_pretrained on this adapter instead of "
        "creating a fresh LoRA adapter; the adapter config governs "
        "rank/alpha/dropout.",
    )

    parser.add_argument(
        "--window-size","""
assert old_arg in src
src = src.replace(old_arg, new_arg)

# 3. Branch the model load in main().
old_load = """    model, tokenizer = load_model_and_tokenizer(
        args.model,
        args.lora_r,
        args.lora_alpha,
        args.lora_dropout,
    )"""
new_load = """    if args.resume_adapter:
        print(f"Resuming from adapter: {args.resume_adapter}")
        print("NOTE: adapter config governs rank/alpha/dropout; "
              "--lora-* flags are ignored on the resume path.")
        tokenizer = AutoTokenizer.from_pretrained(args.model)
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            torch_dtype="auto",
            device_map="auto",
        )
        model.config.use_cache = False
        model = PeftModel.from_pretrained(model, args.resume_adapter, is_trainable=True)
        model.train()
    else:
        model, tokenizer = load_model_and_tokenizer(
            args.model,
            args.lora_r,
            args.lora_alpha,
            args.lora_dropout,
        )"""
assert old_load in src
src = src.replace(old_load, new_load)

open(DST, "w").write(src)
print("wrote %s" % DST)
# Structural checks.
dst = open(DST).read()
for needle in ["--resume-adapter", "PeftModel.from_pretrained",
               "Resuming from adapter", "PeftModel,"]:
    assert needle in dst, needle
print("RESUME PATCH: STRUCTURAL CHECKS PASS (GPU fixture still pending)")

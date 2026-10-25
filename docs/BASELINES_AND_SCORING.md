# Baselines and scoring

This file describes how every score here was produced. The training scripts themselves and the system prompt files are not included. The settings below are exact.

## Scoring by label likelihood

Classification scores use label likelihood. The model reads a request and the candidate labels, and the label with the highest summed label-token log-probability wins. The chat template is used, thinking is disabled, and the model answers by likelihood, not by free generation. The same scoring is used for the frozen model, the told-rule check, the in-context baseline, and the trained adapters, so the arms are comparable.

## Frozen base

The frozen model is Qwen3-0.6B with no training. Its prompt names only the labels and does not define them. A prompt that defined all ten labels by their features would already contain the rules. Frozen scores, held-out out of 100, are authority 23, compliance 19, violation 15. Frozen per-label scores on violation held-out are EMERGENCY_OVERRIDE_LOG 15 out of 15, with every other label at 0.

## Told-rule check

The told-rule check gives the frozen model the rule stated as a paragraph and scores the same held-out items. It answers a narrow question: can the rule be conveyed in words at all? Held-out out of 100, told scores are authority 35, compliance 17, violation 49. Only violation gains clearly from being told the rule. Authority gains 12 and compliance loses 2 against their frozen scores. The original told-rule bar of 80 is met by no rule. A stronger told prompt, with full definitions and worked examples, was not run: it would test prompt design, not the benchmark.

## In-context baseline

The in-context baseline is the frozen Qwen3-0.6B model with a window of recent train items, each shown as a request plus its true label, inserted before the held-out item in stream order. The primary window is 20 items. Windows 5 and 50 are sensitivity windows, run on the same held-out items. Only held-out items are scored. Scoring train items would measure retrieval of items already in the window, not learning. The same construction on patternless control held-out items, with the window drawn from patternless control train items, gives the in-context patternless arm. If in-context learning gained on both real and control held-out items, its gain would be accumulation, not rule learning.

In-context window-20 held-out scores, out of 100, are authority 31, 31, 10; compliance 10, 5, 5; violation 35, 35, 36. Control arms are authority 41, 54, 26; compliance 31, 10, 10; violation 30, 38, 28. Online training wins over in-context learning on every rule. Sensitivity windows were unstable, with compliance seed 2 scoring 50 at window 5 against 5 at window 20, and violation seed 2 scoring 60 at window 50 against 36 at window 20.

## Online training

Training uses low-rank updates on Qwen3-0.6B, learning rate 1e-4, one gradient step per example, and a window of 20 recent items. Each item is scored before its update, so the training curve is a true online curve: the score on an item never benefits from training on that same item. Training runs are unseeded, which leaves seed-to-seed variance partly unexplained.

Four arms are reported for every rule and seed, all on identical held-out items:

- BASE: the frozen model, described above.
- FRESH: after one training pass over the 200 train items, scored out of 100 on held-out items.
- REPEATED: after a second pass over the same 200 train items, scored out of 200 on train items. This arm mixes rule learning with memorization of repeated items.
- PATTERNLESS: after training on the broken-link control stream instead of the real stream, scored out of 100 on control held-out items.

PRIMARY is FRESH minus PATTERNLESS. The pre-stated bar for the main claim was a PRIMARY gain of at least 15. Every rule and every seed clears that bar by a wide margin, with PATTERNLESS at 0 on every rule and seed. The decomposition also reports FRESH minus BASE as the gain from training. Because PATTERNLESS is 0 throughout, the trained gain is not format learning.

## Agent pilot scoring

The agent pilot uses three task types with fixed tool sequences: status_check with 2 steps, compliance_review with 5 steps, and restock_order with 6 steps. The pilot holds 99 train episodes and 46 held-out episodes, 681 steps in total. Scoring is teacher-forced: at each step the model predicts the next tool, the correct tool is then executed for real, so the trajectory stays on the correct path. Results are reported as correct steps and as full-episode success, overall and on the held-out segment. The frozen agent arm comes from the agent script itself with updates and example appending disabled, not from the classification scores. The in-context agent arm uses a capped last-20 window because an uncapped window timed out after 2 hours. Free-run scoring was not measured.

Held-out segment, 215 steps across 46 episodes: frozen 62 steps and 0 episodes; online training 202 steps and 36 episodes; capped in-context 46 steps and 0 episodes. Overall, 681 steps across 145 episodes: frozen 195 steps and 0 episodes; online training 642 steps and 122 episodes; capped in-context 177 steps and 20 episodes.

## Scale check

The scale check repeats the violation seed 0 decomposition with Qwen3-8B, identical except for the model. Frozen 65, fresh 100, patternless 0, PRIMARY 100. The frozen 8B score of 65 comes entirely from three labels at their ceiling, with DENY at 0 out of 35. Training takes DENY from 0 out of 35 to 35 out of 35. That DENY isolation is the scale observation: the larger frozen model already solves three of the four violation labels, and training supplies exactly the missing one. The scale check covers one rule and one seed only.

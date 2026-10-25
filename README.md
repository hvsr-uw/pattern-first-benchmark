# Pattern-first benchmark for continual learning

## In short

I am building a test for continual learning. The test checks whether a small model can learn a rule from a stream of tasks and reuse it on new tasks. Most tests only report an average score, which can come from memorization or from learning the format. This test separates real rule learning from memorization and format learning.

## What this is

This is a benchmark for continual learning, plus the first results measured with it. The question behind it is simple: when a small model improves across a stream of examples, did it learn a reusable rule, or did it only memorize examples and pick up surface format? The benchmark is built so that those two stories can be told apart, in counts, on held-out items the model never trained on.

The thesis is this: online parameter updates let a small model acquire a stated decision rule from a stream and reuse it on unseen instances of the same rule, while frozen and in-context baselines do not. It holds strongly for one rule, partly for a second rule, and unstably for a third rule. The claim is the difference between rules, not a uniform win across all rules.

## The three rules

Every stream here follows exactly one stated decision rule. The rules come from the label meanings of a company approval workflow, where a request is mapped to one action label. The three rules divide the ten labels exactly, with no label in two rules.

### Authority: approval decisions

Five labels. The rule decides what to do about approval and paperwork, using the authority gap, the approval form, and whether the paperwork is complete.

- AUTO_APPROVE: the requester's authority exceeds what is needed, approval is written, paperwork is complete, there is no pressure, and the impact is low or moderate.
- CONDITIONAL_APPROVE: the requester's authority exactly meets what is needed, approval is written, paperwork is complete, and there is no pressure.
- APPROVE_WITH_LOG: the requester's authority exceeds what is needed, approval is written, paperwork is complete, there is no pressure, and the item is high impact or safety-critical, but not in a regulated domain.
- VERIFY_APPROVAL: the requester's authority is just short of what is needed, or the approval is only verbal.
- VERIFY_DOCUMENTATION: the requester has enough authority, but the paperwork is incomplete or there is deadline pressure.

Regulated-domain instances are excluded from authority streams, so authority and compliance streams do not overlap.

### Compliance: routing to compliance

One main label, with two branches.

- Branch one, sign-off absent: the item is in a regulated domain (export control or personal data) and no compliance sign-off is on record, so the label is ROUTE_TO_COMPLIANCE.
- Branch two, sign-off present: the item is in a regulated domain and a clean compliance sign-off is on record, so the label falls back to the authority table above.

A compliance stream with only one branch would be invalid, because a model could win it by predicting one label every time. The two branches are kept at a stated ratio of 50 and 50.

### Violation: handling violations

Four labels. The rule decides what to do when a request breaks or bends the normal process.

- EMERGENCY_OVERRIDE_LOG: a genuine active emergency plus an explicit bypass request.
- ESCALATE_TO_LEADERSHIP: a high-impact violation, meaning an explicit bypass or threshold-gaming pattern on a high-impact item with no regulatory angle, or a safety-critical request where the requester's authority is well short.
- DENY: a clear non-emergency violation on a low or moderate impact item.
- REQUEST_ADDITIONAL_INFO: the amount, the approver, or the documentation status is unstated, so the request cannot be classified at all. This label is a completeness detector, not a violation judgment. It is reported as its own sub-metric inside violation results.

Impact tiers are stated in advance: tiers 4 and 5 count as high impact, tiers 1 to 3 count as low or moderate impact.

## The protocol

Each rule is measured the same way.

1. One stated rule per stream. The rule is written down before any training or scoring. The model is never asked to guess what the rule might be.
2. Held-out same-rule test. After training on 200 stream items, the model is tested on 100 new items that follow the same rule and never appeared in training. Held-out item sets are fixed across seeds, with train order shuffled per seed.
3. Patternless control. A second stream is built from the exact same request texts, but the labels are reassigned by a fixed cycle, so no item's label follows the rule its text implies. For authority the cycle runs AUTO_APPROVE, CONDITIONAL_APPROVE, APPROVE_WITH_LOG, VERIFY_APPROVAL, VERIFY_DOCUMENTATION, and back to AUTO_APPROVE. For violation the cycle runs EMERGENCY_OVERRIDE_LOG, ESCALATE_TO_LEADERSHIP, DENY, REQUEST_ADDITIONAL_INFO, and back to EMERGENCY_OVERRIDE_LOG. For compliance the two branches are swapped, which preserves the label distribution exactly. If training on this broken-link stream still improved held-out scores, the gain would be format learning or accumulation, not rule learning. The main metric, PRIMARY, is the trained score minus the patternless score, both out of 100. The pre-stated bar for the main claim was a PRIMARY gain of at least 15.
4. Paraphrase test. A second held-out set of 100 items per rule keeps the same features and labels but uses entirely new wording, with no shared 12-word sequence with any same-rule train text and no signature phrase from the original templates. If the gain survives new wording, the model learned something beyond the original templates. If it collapses, the gain was template-cue learning.
5. Delayed retention test. After training on one rule and testing, training continues on 100 items of a different rule, or on 100 broken-link control items, and the first rule is tested again on identical items. The drop from first test to re-test is the retention measure. See docs/RETENTION.md for the arms and the result.

## How learning was measured

Four arms are reported for every rule and seed, all on identical held-out items, in counts out of 100 unless stated otherwise.

- BASE: the frozen model, with no training, scored by label likelihood using a prompt that names only the labels. The prompt does not define the labels, so the frozen score does not already contain the rules.
- FRESH: the model after one online training pass over the 200 train items. Training uses Qwen3-0.6B, low-rank updates, learning rate 1e-4, one gradient step per example, and a window of 20 recent items. Each item is scored before its update, so the training curve is a true online curve.
- REPEATED: the model after a second pass over the same 200 train items, scored out of 200. This arm mixes rule learning with memorization of repeated items.
- PATTERNLESS: the model after training on the broken-link control stream instead of the real stream.

The decomposition is simple: FRESH minus BASE is the gain from training, and FRESH minus PATTERNLESS is PRIMARY, the gain beyond format learning. A rule is admitted to the benchmark when online training reaches at least 80 correct out of 100 on same-template held-out items AND beats the frozen model on identical items by at least 20, on at least two of three seeds. All three rules are admitted under that standard. Authority passes on 2 of 3 seeds.

Two further baselines are reported. The told-rule check gives the frozen model the rule stated as a paragraph and measures whether the rule can be conveyed in words at all. The in-context baseline gives the frozen model a window of recent train items (20 as the primary window, 5 and 50 as sensitivity windows) and measures whether examples in context alone can match training. Online training is compared against in-context learning as well as against the frozen model.

The agent lane is a pilot. It uses three task types with fixed tool sequences: status_check (2 steps), compliance_review (5 steps), and restock_order (6 steps). Scoring is teacher-forced: the model predicts the next tool, the correct tool is then executed for real, so the trajectory stays on the correct path. Results are reported as correct steps and as full-episode success, overall and on the held-out segment. Free-run scoring, where the model's own tools drive the trajectory, was not measured.

## Headline results, in counts

Same-template held-out, out of 100, all seeds, all rules.

| Rule | Frozen | Fresh seed 0 | Fresh seed 1 | Fresh seed 2 | Patternless, all seeds | PRIMARY seed 0 | PRIMARY seed 1 | PRIMARY seed 2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Violation | 15 | 100 | 100 | 100 | 0 | 100 | 100 | 100 |
| Compliance | 19 | 99 | 100 | 95 | 0 | 99 | 100 | 95 |
| Authority | 23 | 100 | 100 | 76 | 0 | 100 | 100 | 76 |

Repeated-train scores, out of 200: violation 200 on all seeds, compliance 200, 200, 190, authority 200, 200, 152.

Paraphrase gain, meaning the trained score minus the frozen score on identical paraphrase items, out of 100. Frozen paraphrase scores are violation 31, compliance 22, authority 12.

| Rule | Seed 0 | Seed 1 | Seed 2 |
| --- | --- | --- | --- |
| Violation | 65 | 69 | 41 |
| Compliance | 41 | 51 | 38 |
| Authority | 35 | 58 | 8 |

Compliance paraphrase is carried entirely by the routing branch: ROUTE_TO_COMPLIANCE scores 50 out of 50 on all seeds, while the fallback branch scores 13 out of 50, 23 out of 50, and 10 out of 50.

In-context baseline, window 20, held-out out of 100: authority 31, 31, 10; compliance 10, 5, 5; violation 35, 35, 36. Online training wins over in-context learning on every rule. Sensitivity windows were unstable: compliance seed 2 scores 50 at window 5 against 5 at window 20, and violation seed 2 scores 60 at window 50 against 36 at window 20. That instability is a finding about the in-context baseline.

Agent pilot, teacher-forced, held-out segment of 215 steps across 46 episodes: frozen 62 steps and 0 episodes; online training 202 steps and 36 episodes; capped in-context learning with a last-20 window 46 steps and 0 episodes. Overall, across 681 steps and 145 episodes: frozen 195 steps and 0 episodes; online training 642 steps and 122 episodes; capped in-context 177 steps and 20 episodes. The in-context agent arm uses a capped last-20 window because an uncapped window timed out after 2 hours.

Scale check, violation seed 0 only: the 8B model scores frozen 65, fresh 100, patternless 0, PRIMARY 100. The frozen 8B score of 65 comes entirely from three labels: EMERGENCY_OVERRIDE_LOG 15 out of 15, ESCALATE_TO_LEADERSHIP 30 out of 30, and REQUEST_ADDITIONAL_INFO 20 out of 20, with DENY 0 out of 35. Training fixes DENY, taking it from 0 out of 35 to 35 out of 35, while the other labels stay at their frozen scores. That DENY isolation is the sharpest single scale observation.

Retention, authority seed 0, out of 100: first test 100. After 100 intervening items of a different rule, re-test 100, drop 0. After 100 intervening broken-link control items, re-test 33, drop 67. The comparison between those two drops does not support a forgetting claim or a drift claim, because the design expected the different-rule arm to drop more than the drift arm, and the opposite happened. Absolute retention after a different rule is 100 out of 100, and the broken-link intervening stream drops the adapter to 33. See docs/RETENTION.md.

Told-rule diagnostic, held-out out of 100: frozen violation 15 and told 49, frozen authority 23 and told 35, frozen compliance 19 and told 17. Only violation is conveyable as a paragraph. Authority and compliance are acquirable by training only, not by being told the rule. The original told-rule bar of 80 is not met by any rule.

## Limitations

- Authority is unstable across seeds. Same-template fresh scores are 100, 100, 76, and paraphrase gains are 35, 58, 8. Seed 2 collapses on VERIFY_DOCUMENTATION, scoring 1 out of 25 held-out and 2 out of 50 train, systematically predicting CONDITIONAL_APPROVE. Scoring is deterministic, so this is training variance, and training runs are unseeded.
- Compliance paraphrase is branch-structured. The routing branch is perfect on paraphrase, the fallback branch is weak.
- The agent results are teacher-forced only. Free-run performance, where the model's own tool choices drive the trajectory, was not measured.
- The scale check is thin. The 8B check covers one rule and one seed only.
- The retention comparison does not support a forgetting claim or a drift claim.
- The control fairness check has a weakness. The matched-distribution control totals pass on all three rules, and the told-rule model gains nothing on the control streams, but a stricter per-label version of the check does not pass for compliance and violation. That weakness is described in docs/KEY_DECISIONS.md.

## Files

- streams/: nine 600-row stream files, 3 rules times 3 seeds. Each file holds 200 train items, 100 held-out items, 200 patternless control train items, and 100 patternless control held-out items.
- paraphrase/: three 100-row paraphrase held-out files, one per rule.
- pilot/: the agent pilot, 99 train episodes and 46 held-out episodes, 681 steps in total.
- results/: main_results.csv with the main counts for every rule and seed, plus one CSV per figure. See docs/RESULTS_GUIDE.md for what each file means.
- scripts/: the stream generator, the paraphrase generator, the scoring scripts, the in-context scoring script, the decomposition calculator, the agent pilot filter, and the training-resume patch builder. The training scripts themselves and the system prompt files are not included; the docs give the exact settings used.
- docs/: the stream specification, the baselines and scoring description, the retention record, the results guide, and the key decisions record.

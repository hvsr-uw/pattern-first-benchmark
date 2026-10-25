# Results guide

This file explains what each results file means and states the key counts. All scores are counts.

## main_results.csv

One row per rule and seed, plus one row for the 8B violation check. Columns, in order: rule, seed, frozen score, fresh score, patternless score, PRIMARY, paraphrase gain, in-context window-20 score, paraphrase frozen score. Held-out scores are out of 100. PRIMARY equals fresh minus patternless. Paraphrase gain equals the trained paraphrase score minus the frozen paraphrase score, on identical paraphrase items.

| Rule | Seed | Frozen | Fresh | Patternless | PRIMARY | Paraphrase gain | In-context window 20 | Paraphrase frozen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Violation | 0 | 15 | 100 | 0 | 100 | 65 | 35 | 31 |
| Violation | 1 | 15 | 100 | 0 | 100 | 69 | 35 | 31 |
| Violation | 2 | 15 | 100 | 0 | 100 | 41 | 36 | 31 |
| Compliance | 0 | 19 | 99 | 0 | 99 | 41 | 10 | 22 |
| Compliance | 1 | 19 | 100 | 0 | 100 | 51 | 5 | 22 |
| Compliance | 2 | 19 | 95 | 0 | 95 | 38 | 5 | 22 |
| Authority | 0 | 23 | 100 | 0 | 100 | 35 | 31 | 12 |
| Authority | 1 | 23 | 100 | 0 | 100 | 58 | 31 | 12 |
| Authority | 2 | 23 | 76 | 0 | 76 | 8 | 10 | 12 |
| Violation, 8B | 0 | 65 | 100 | 0 | 100 | not measured | not measured | not measured |

Violation is strong on every arm. Compliance is strong on same-template items and partial on paraphrase, where the routing branch carries the gain. Authority is strong on seeds 0 and 1 and unstable on seed 2, on both same-template and paraphrase items.

## fig1_decomp.csv

The decomposition table. Columns: rule, seed, BASE out of 100, FRESH out of 100, REPEATED out of 200, PATTERNLESS out of 100, pattern gain, format gain, PRIMARY. Pattern gain equals FRESH minus BASE. PRIMARY equals FRESH minus PATTERNLESS. Repeated scores, out of 200, are violation 200 on all seeds, compliance 200, 200, 190, authority 200, 200, 152. The 8B violation row reads frozen 65, fresh 100, repeated 200, patternless 0, PRIMARY 100.

## fig2_gains.csv

The same-template versus paraphrase comparison. Columns: rule, seed, same-template gain, paraphrase gain, gap. Same-template gain equals FRESH minus BASE. Paraphrase gain equals the trained paraphrase score minus the frozen paraphrase score. Gap equals same-template gain minus paraphrase gain. The gap is the cost of new wording: violation 20, 16, 44; compliance 39, 30, 38; authority 42, 19, 45. A large gap means the same-template gain depended partly on the original wording. Authority seed 2 has the largest same-template to paraphrase collapse in absolute terms, from a same-template gain of 53 to a paraphrase gain of 8.

## fig3_agent.csv

The agent pilot table. Columns: mode, held-out steps correct, held-out steps total, held-out episodes correct, held-out episodes total, overall steps correct, overall steps total, overall episodes correct, overall episodes total. Modes are frozen, online training, and capped in-context with a last-20 window. Held-out segment: frozen 62 out of 215 steps and 0 out of 46 episodes; online training 202 out of 215 steps and 36 out of 46 episodes; capped in-context 46 out of 215 steps and 0 out of 46 episodes. Overall: frozen 195 out of 681 steps and 0 out of 145 episodes; online training 642 out of 681 steps and 122 out of 145 episodes; capped in-context 177 out of 681 steps and 20 out of 145 episodes. Scoring is teacher-forced throughout; see docs/BASELINES_AND_SCORING.md.

## fig4_scale.csv

The scale table. Columns: model, frozen score, fresh score, patternless score, PRIMARY, frozen DENY out of 35, fresh DENY out of 35. Qwen3-0.6B reads frozen 15, fresh 100, patternless 0, PRIMARY 100, DENY frozen 0 out of 35, DENY fresh 35 out of 35. Qwen3-8B reads frozen 65, fresh 100, patternless 0, PRIMARY 100, DENY frozen 0 out of 35, DENY fresh 35 out of 35. The scale observation is the DENY isolation: both model sizes need training to solve DENY, and training supplies exactly that label.

## fig5_retention.csv

The retention table. Columns: arm, first test, re-test, drop. Arm 1, intervening different rule: 100, 100, drop 0. Arm 2, intervening broken-link control: 100, 33, drop 67. Arm 1 versus Arm 2 does not support a forgetting claim: Arm 2 behaves as an adversarial intervention, not as a drift control. Arm 1 absolute retention and Arm 2 plasticity are separate observations. See docs/RETENTION.md.

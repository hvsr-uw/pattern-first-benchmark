# Key decisions

Each standard below states the bar and the outcome. Stricter readings are noted where they change the outcome.

## Admission gate: at least two of three seeds

A rule is admitted to the benchmark when online training reaches at least 80 correct out of 100 on same-template held-out items AND beats the frozen model on identical items by at least 20, on at least two of three seeds. All three rules are admitted. Authority passes on 2 of 3 seeds, with same-template fresh scores of 100, 100, and 76. Under a strict all-seeds reading, authority would not be admitted. The told-rule bar below is separate from the admission gate, and no rule meets it.

## Told-rule diagnostic

The told-rule check is a diagnostic, not an admission standard. It measures whether a rule stated as a paragraph lifts the frozen model. Told minus frozen scores are violation 34, authority 12, compliance negative 2. Told scores above chance are violation 24, authority 15, compliance 0, where chance is the largest single-label share of the held-out set. Only violation is conveyable as a paragraph. Authority and compliance are acquirable by training only. A stronger told prompt was not run, for the reason given in docs/BASELINES_AND_SCORING.md.

## Control fairness

Control fairness is judged by two checks. The first check compares frozen scores on control streams with frozen scores on real streams, after matching the label distributions, within a pre-stated tolerance of 10. That check passes on all three rules. The second check requires the told-rule model to gain nothing on control streams. Told control scores are authority 25, compliance 5, violation 30, all below the told real scores of authority 35, compliance 17, violation 49, and below the frozen control scores of authority 30, compliance 10, violation 36. That check passes on all three rules.

A stricter per-label version of the first check, which compares balanced per-label frozen rates within the same tolerance, does not pass for compliance and violation. Compliance control label counts are identical to real label counts, yet the per-label check still fails, which shows the per-label check measures the frozen model's prior times the cycle alignment, not distribution matching. Frozen per-label rates are extreme, at 0 or full marks on most labels, so balanced rates amplify single-label flips. Difficulty matching therefore rests on the matched-total check plus the patternless score of 0 on every rule and seed. The per-label failures are a limitation. Under the stricter both-required reading, control fairness would fail for compliance and violation.

## Agent in-context arm

The in-context agent arm uses a last-20 window because an uncapped window timed out after 2 hours.

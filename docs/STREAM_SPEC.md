# Stream specification

This file states the rules, the stream construction, and the validation gates. The rules were written down before any training or scoring. Changing a rule after seeing results would require a version change and a written note stating what changed and why. All reports use counts, never percentages.

## Feature vocabulary

Every request is described by the same features, shared across rules: authority gap (exceeds, exactly meets, just short, well short), approval form (written, verbal), paperwork (complete, incomplete), pressure (none, deadline pressure), emergency (genuine active safety or regulatory emergency, ordinary urgency, none), regulated domain (export control, personal data, none), compliance sign-off (absent, clean on record), bypass or threshold-gaming pattern (present, absent), and impact tier (1 to 2 low, 3 moderate, 4 substantial, 5 severe or critical). Impact boundary, stated in advance: tiers 4 and 5 count as high impact, tiers 1 to 3 count as low or moderate impact.

## Authority: approval decisions

Regulated-domain instances are excluded, so authority and compliance streams do not overlap. The APPROVE_WITH_LOG branch is therefore restricted to high-impact or safety-critical non-regulated instances. Regulated instances with specialist sign-off belong to compliance, not authority.

- Exceeds, written, complete, no pressure, low or moderate impact leads to AUTO_APPROVE.
- Exactly meets, written, complete, no pressure leads to CONDITIONAL_APPROVE.
- Exceeds, written, complete, no pressure, high impact or safety-critical, non-regulated, leads to APPROVE_WITH_LOG.
- Just short, or approval only verbal, leads to VERIFY_APPROVAL.
- Enough authority, with incomplete paperwork or deadline pressure, leads to VERIFY_DOCUMENTATION.

## Compliance: routing to compliance

Two branches, at a stated ratio of 50 and 50.

- Regulated domain, compliance sign-off absent, leads to ROUTE_TO_COMPLIANCE. This is branch one.
- Regulated domain, clean compliance sign-off on record, leads back to the authority table. This is branch two.

A single-branch compliance stream is invalid, because a model could win it by predicting one label every time.

## Violation: handling violations

REQUEST_ADDITIONAL_INFO is its own sub-metric inside violation results.

- Genuine active emergency plus an explicit bypass request leads to EMERGENCY_OVERRIDE_LOG.
- High-impact violation leads to ESCALATE_TO_LEADERSHIP. That means an explicit bypass or threshold-gaming pattern on a high-impact item with no regulatory angle, or a safety-critical request where authority is well short.
- Clear non-emergency violation on a low or moderate impact item leads to DENY.
- Amount, approver, or documentation status unstated, so the request cannot be classified at all, leads to REQUEST_ADDITIONAL_INFO.

## Stream sizes and splits

Per rule, per seed:

- Train: 200 instances.
- Held-out: 100 instances. Held-out item sets are fixed across seeds, with train order shuffled per seed. Held-out items never appear in any train split.
- Patternless control train: 200 instances, using the same request texts as the rule train split, with labels reassigned by a fixed cycle so no item's label follows the rule its text implies. Authority cycle: AUTO_APPROVE, CONDITIONAL_APPROVE, APPROVE_WITH_LOG, VERIFY_APPROVAL, VERIFY_DOCUMENTATION, and back to AUTO_APPROVE. Violation cycle: EMERGENCY_OVERRIDE_LOG, ESCALATE_TO_LEADERSHIP, DENY, REQUEST_ADDITIONAL_INFO, and back to EMERGENCY_OVERRIDE_LOG. Compliance: the two branches are swapped, which preserves the label distribution exactly. The control therefore preserves surface wording exactly and breaks the text-to-label link. It rules out format and accumulation gain. It does not by itself separate rule learning from surface-cue learning; the paraphrase held-out arm tests that.
- Patternless control held-out: 100 instances, same construction.
- Intervening stream for retention: 100 instances of a different rule, or 100 patternless control instances.
- Re-test items: identical to the first-test held-out items, same identifiers.

Seeds are 0, 1, and 2. Each seed changes train order and template sampling. Held-out item sets are fixed across seeds.

## Paraphrase held-out construction

Paraphrase held-out sets hold 100 items per rule. Features and labels are identical to the source held-out items. Surface wording is entirely new. No paraphrase text shares a 12-word sequence with any same-rule train text, and no paraphrase text contains a signature phrase from the original templates. Paraphrase item identifiers are disjoint from train identifiers, and paraphrase texts are unique within the set. Label counts in each paraphrase set exactly equal the source held-out label counts: authority 10, 20, 20, 25, 25 across its five labels in table order; compliance ROUTE_TO_COMPLIANCE 50 plus fallback 5, 15, 10, 10, 10; violation 15, 30, 35, 20 across its four labels in table order.

## File format and naming

Stream files live in streams/ and are named by rule and seed, one JSON object per line, with fields: identifier, request text, features (the structured vocabulary above), label, rule, branch (for compliance branches and the violation sub-metric), split (train, held-out, patternless control train, patternless control held-out, intervening), and seed. Paraphrase files live in paraphrase/ with the same fields.

## Validation gates

Every generated file set must pass these gates before use:

- Held-out identifiers are disjoint from train identifiers.
- Label counts per split match the stated ratio within 5 instances. Compliance branches sit within 5 of 50 and 50.
- Patternless control label distribution matches the real-stream train distribution within 5 instances per label.
- Request texts are unique within a split, with no exact duplicates.
- Paraphrase sets pass the 12-word sequence gate and the signature-phrase gate described above.

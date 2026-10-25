# Retention record

This file describes the retention test, its arms, and its result.

## Design

All arms re-test authority held-out items with identical items at first test and re-test. The intervening stream is fixed at 100 instances in every arm. Continued training means resuming from the trained adapter and keeping training, not training a fresh adapter on the intervening stream. Every stage output was checked for row counts of 100.

- Arm 1, retention: train on authority, test authority held-out, continue training the same adapter on 100 compliance train items, re-test authority held-out. Drop equals first test minus re-test.
- Arm 2, drift control: train on authority, test, continue training on 100 patternless control items, re-test. If the Arm 1 drop and the Arm 2 drop are equal, the drop is drift from continued training itself, not forgetting of the first rule. If the Arm 1 drop exceeds the Arm 2 drop, the excess is the forgetting signal.
- Arm 3, interference probe: before the intervening stream, test compliance held-out items with the authority-trained adapter. If authority training already hurts compliance items before compliance is taught, that is pre-block interference, reported separately.

## Result, authority seed 0, out of 100

- First test: 100.
- Arm 3, authority adapter on compliance held-out: 40. ROUTE_TO_COMPLIANCE scores 0 out of 50, the fallback branch scores 40 out of 50, with APPROVE_WITH_LOG at 0 out of 10. Authority training does not transfer to compliance routing; the routing label is entirely missed before compliance is taught.
- Arm 1 re-test: 100. Drop 0.
- Arm 2 re-test: 33. Drop 67. The Arm 2 damage is concentrated: APPROVE_WITH_LOG 0 out of 20, CONDITIONAL_APPROVE 0 out of 20, VERIFY_APPROVAL 0 out of 25, VERIFY_DOCUMENTATION 25 out of 25, AUTO_APPROVE 8 out of 10.

## What the comparison shows

The design expected the different-rule arm to drop more than the drift arm. The opposite happened. The different-rule intervening stream caused no drop at all, while the broken-link intervening stream caused a drop of 67. The two drops therefore do not support a forgetting claim or a drift claim: the broken-link arm behaves as an adversarial intervention, not as a neutral drift control, so the two drops cannot be subtracted to isolate forgetting.

Absolute retention after a different rule is 100 out of 100: the adapter kept the first rule perfectly through 100 items of a second rule. And a broken-link intervening stream sharply damages the adapter, taking it from 100 to 33.

## What would be needed for a valid retention claim

A repaired comparison would need a drift control that is neutral by construction, meaning an intervening stream that continues training without teaching a conflicting mapping and without breaking the label link, plus a demonstration that the control behaves neutrally on a rule it should not affect. Until such a control exists and behaves as designed, the retention test does not support a retention claim.

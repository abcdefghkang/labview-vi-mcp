| file | errors | warnings | codes |
|---|---:|---:|---|
| `round3/clamp-demo.aixml.xml` | 0 | 1 | uid-low |
| `round3/clamp-value.aixml.xml` | 0 | 1 | uid-low |
| `round3/saturating-accumulator-v2.aixml.xml` | 0 | 1 | uid-low |
| `round3/saturating-accumulator.aixml.xml` | 3 | 1 | lv003-sr-seed-inside-loop, uid-low |
| `round3/variant-a-nocase.aixml.xml` | 3 | 2 | lv003-sr-seed-inside-loop, net-unconsumed, uid-low |
| `round3/variant-b-noindex.aixml.xml` | 3 | 1 | lv003-sr-seed-inside-loop, uid-low |
| `round3/variant-c-panelstop.aixml.xml` | 3 | 3 | comment-may-be-clipped, lv003-sr-seed-inside-loop, net-unconsumed, uid-low |
| `round3/variant-d-rootseds.aixml.xml` | 0 | 1 | uid-low |
| `round3/variant-e-mixedseeds.aixml.xml` | 2 | 1 | lv003-sr-seed-inside-loop, uid-low |
| `round4/batch-averager-empty-exported.aixml.xml` | 0 | 1 | uid-low |
| `round4/batch-averager-empty.aixml.xml` | 0 | 2 | net-unconsumed, uid-low |
| `round4/batch-averager-exported.aixml.xml` | 0 | 1 | uid-low |
| `round4/batch-averager.aixml.xml` | 0 | 2 | net-unconsumed, uid-low |
| `round4/probe-frame-sr-read.aixml.xml` | 1 | 2 | net-unconsumed, net-unproduced, uid-low |
| `round4/probe-string-case.aixml.xml` | 0 | 1 | uid-low |
| `round4/ref-state-machine-fundamentals.aixml.xml` | 0 | 5 | comment-may-be-clipped, uid-low |
| `round5/batch-averager-scaled.aixml.xml` | 0 | 2 | net-unconsumed, uid-low |
| `round5/clamp-demo.aixml.xml` | 0 | 1 | uid-low |
| `round5/clamp-value.aixml.xml` | 0 | 1 | uid-low |
| `round5/deep-export.aixml.xml` | 0 | 1 | uid-low |
| `round5/scaled-export.aixml.xml` | 0 | 1 | uid-low |
| `round6/node-probe/array-extra.aixml.xml` | 0 | 1 | uid-low |
| `round6/node-probe/array-ops.aixml.xml` | 0 | 4 | net-unconsumed, uid-low |
| `round6/node-probe/bundle-empty.aixml.xml` | 0 | 1 | uid-low |
| `round6/node-probe/bundle-only.aixml.xml` | 0 | 1 | uid-low |
| `round6/node-probe/bundle-typed-base.aixml.xml` | 0 | 1 | uid-low |
| `round6/node-probe/cluster-literal.aixml.xml` | 0 | 1 | uid-low |
| `round6/node-probe/cluster-ops.aixml.xml` | 0 | 1 | uid-low |
| `round6/retarget-evidence/caller-n.aixml.xml` | 0 | 1 | uid-low |
| `round6/retarget-evidence/caller-p2.aixml.xml` | 0 | 1 | uid-low |
| `round6/retarget-evidence/caller-z.aixml.xml` | 0 | 1 | uid-low |
| `round6/retarget-evidence/export-callerF.xml` | 0 | 1 | uid-low |
| `round6/retarget-evidence/export-swapped.xml` | 0 | 1 | uid-low |
| `round6/retarget-evidence/kappa.aixml.xml` | 0 | 1 | uid-low |
| `round6/retarget-evidence/zeta.aixml.xml` | 0 | 1 | uid-low |
| `round6/state-machine/heartbeat.aixml.xml` | 0 | 1 | uid-low |
| `round6/state-machine/traffic-light.aixml.xml` | 0 | 1 | uid-low |
| `round6/state-machine/washing-machine.aixml.xml` | 0 | 1 | uid-low |
| `round7/bind-helper/bind-helper-instr-v1.aixml.xml` | 0 | 6 | net-unconsumed, uid-low |
| `round7/bind-helper/bind-helper-instr-v2.aixml.xml` | 0 | 8 | net-unconsumed, uid-low |
| `round7/fixtures/Configure.aixml.xml` | 1 | 3 | conn-required-output, net-unconsumed, uid-low |
| `round7/fixtures/Monitor.aixml.xml` | 1 | 3 | conn-required-output, net-unconsumed, uid-low |
| `round7/fixtures/Race1.aixml.xml` | 1 | 3 | conn-required-output, net-unconsumed, uid-low |
| `round7/fixtures/Race2.aixml.xml` | 1 | 3 | conn-required-output, net-unconsumed, uid-low |
| `round7/fixtures/Tune.aixml.xml` | 1 | 3 | conn-required-output, net-unconsumed, uid-low |
| `round7/next-probes/p3-cluster-payload.aixml.xml` | 0 | 1 | comment-may-be-clipped |
| `round7/next-probes/p4-two-events-one-registration.aixml.xml` | 1 | 5 | comment-may-be-clipped, net-typo, net-unconsumed |
| `round7/next-probes/p5-valuechange-timeout-frames.aixml.xml` | 0 | 5 | comment-may-be-clipped, net-unconsumed |

| code | count |
|---|---:|
| `uid-low` | 45 |
| `net-unconsumed` | 37 |
| `lv003-sr-seed-inside-loop` | 14 |
| `comment-may-be-clipped` | 10 |
| `conn-required-output` | 5 |
| `net-unproduced` | 1 |
| `net-typo` | 1 |

**50 AIXML document(s), 48 with findings: 21 error(s), 92 warning(s), 0 info; 9 non-AIXML file(s) skipped (RSRC/FPHb dumps); 6 known false positive(s) suppressed (cond="true"/"false").**

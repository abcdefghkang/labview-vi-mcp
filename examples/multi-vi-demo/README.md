# Multi-VI Demo — top-level VI orchestrating two subVIs (Round 20)

A **multi-VI program** authored entirely as AIXML by an AI agent and run end to end through
the **pylabview-only closure** (no gRPC / Nigel needed — only `LabVIEW.exe` running):

```
Multi VI Demo.vi   (top level: N in; Sum / Count / Mean out)
 ├── Call → Accumulate N.vi   (While Loop + 2 shift registers: Sum = 1+2+…+N, Count = N)
 └── Call → Mean Of Pair.vi   (Divide x/y — int32/int32 promotes to DBL)
```

**Verified by running** (`lvai_run_vi_and_read_values`, `backend:"pylabview"`, via ActiveX):

| N | Sum | Count | Mean | verdict |
|---|-----|-------|------|---------|
| 5 | 15 | 5 | 3.00000000000000 | PASS (hand-computed) |
| 3 | 6 | 3 | 2.00000000000000 | PASS (hand-computed) |

Two different inputs producing two different hand-computed outputs proves **both** Call
directions live (N in through the pane; Sum/Count/Mean back out) — a silently-empty Call
(the LV014 trap) would read 0 for every indicator at both inputs.

## What this round added (beyond the round-6 multi-VI recipe)

1. **Call resolution on the pylabview backend reads the callee FILE, not IDE memory.**
   Neither subVI was ever opened (`openVINote` says the pylabview backend "has no road into
   the IDE"), yet the composer resolved both Calls against the callee connector panes
   (`composerReport`: `Call 'Accumulate N.vi' <- <Element 'TypeDesc'> (pane 4833, 16 slots)`).
   The round-6 rule "subVI first with `openVI:true`" belongs to the **gRPC/NI route**; on the
   pylabview route the requirement is only *ordering*: callee `.vi` files must exist on disk
   (same directory) **before** the caller is composed. `openVI:true` is accepted and ignored.
2. **`lvai_ensure_labview` cold-starts the whole loop.** This round began with NO
   `LabVIEW.exe` running; `lvai_ensure_labview` launched LabVIEW 2026 (64-bit) itself
   (`startedByThisCall:true`, `launchMethod:"explorer"`, LVAutoSave cleared). The gRPC
   service never came up (needs Nigel) and did not matter. Cold machine → run values:
   `ensure_labview → convert ×3 (pylabview) → run (pylabview)` — fully unattended.
3. **Type promotion crosses the subVI boundary.** int32/int32 through `Divide` yields DBL;
   the caller wires that DBL across its own pane to a `double` indicator. Composer accepts,
   run returns `3.00000000000000`.

## Rebuild + run recipe (no gRPC / Nigel needed)

```bash
# 0) G0 offline gate first — must be green before anything else
python tools/audit_aixml.py --summary "examples/multi-vi-demo/Accumulate N.aixml.xml"
python tools/audit_aixml.py --summary "examples/multi-vi-demo/Mean Of Pair.aixml.xml"
python tools/audit_aixml.py --summary "examples/multi-vi-demo/Multi VI Demo.aixml.xml"

# 1) make sure LabVIEW.exe is running (lvai_ensure_labview starts it if not)

# 2) compose subVIs first, THEN the caller (ordering is the rule, not openVI)
lvai_convert_aixml_to_vi(backend:"pylabview", openVI:true,
    aiXmlFilePath:"<repo>/examples/multi-vi-demo/Accumulate N.aixml.xml",
    viPath:"<repo>/examples/multi-vi-demo/Accumulate N.vi")
lvai_convert_aixml_to_vi(backend:"pylabview", openVI:true,
    aiXmlFilePath:"<repo>/examples/multi-vi-demo/Mean Of Pair.aixml.xml",
    viPath:"<repo>/examples/multi-vi-demo/Mean Of Pair.vi")
lvai_convert_aixml_to_vi(backend:"pylabview",
    aiXmlFilePath:"<repo>/examples/multi-vi-demo/Multi VI Demo.aixml.xml",
    viPath:"<repo>/examples/multi-vi-demo/Multi VI Demo.vi")

# 3) run it (two-point verification)
lvai_run_vi_and_read_values(backend:"pylabview",
    viPath:"<repo>/examples/multi-vi-demo/Multi VI Demo.vi", inputsJson:'{"N":"5"}')
#   → Sum=15, Count=5, Mean=3.00000000000000
lvai_run_vi_and_read_values(backend:"pylabview",
    viPath:"<repo>/examples/multi-vi-demo/Multi VI Demo.vi", inputsJson:'{"N":"3"}')
#   → Sum=6, Count=3, Mean=2.00000000000000
```

All three AIXML pass `audit_aixml.py` with **0 errors / 0 warnings** (G0). Evidence
transcripts live in [`research/artifacts/round20/`](../../research/artifacts/round20/);
the round write-up is [`research/29-multi-vi-orchestration-pylabview.md`](../../research/29-multi-vi-orchestration-pylabview.md).

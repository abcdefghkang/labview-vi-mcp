# Nested Multi-VI Demo — a three-level Call chain (Round 21)

A **three-level nested multi-VI program** authored entirely as AIXML by an AI agent and run
end to end through the **pylabview-only closure** (no gRPC / Nigel needed — only
`LabVIEW.exe` running). This is round 20's orchestration pushed one Call deeper: the
middle layer calls a subVI **inside a While Loop**, and that subVI is itself a caller.

```
Nested Chain Demo.vi   (top level: N in; Sum / Count out)
 └── Call → Sum Of Doubles.vi   (While Loop + 2 shift registers + a Call INSIDE the loop:
             Sum = 2+4+…+2N = N·(N+1), Count = N)
      └── Call → Double It.vi   (grandchild: Doubled = 2·x, one Multiply)
```

**Verified by running** (`lvai_run_vi_and_read_values`, `backend:"pylabview"`, via ActiveX):

| N | Sum | Count | verdict |
|---|-----|-------|---------|
| 3 | 12 | 3 | PASS (hand-computed: 2+4+6) |
| 4 | 20 | 4 | PASS (hand-computed: 2+4+6+8) |

The Sum value crosses **four** pane boundaries before it is read (grandchild out, N times;
child out; top out). If the in-loop Call were silently empty (the LV014 trap), every
iteration would add 0 and Sum would read 0 at both inputs while Count still reads N —
`Sum=12/20` with `Count=3/4` couples **both Call hops** to the live data path.

## What this round added (beyond the round-20 orchestration)

1. **Calls compose inside structures, at depth.** The Call to `Double It.vi` sits inside
   `Sum Of Doubles.vi`'s While Loop and composed like a plain node — same round-6 form
   (`composerReport`: `Call 'Double It.vi' <- <Element 'TypeDesc'> (pane 4833, 16 slots)`,
   output net id 4253 independent of the Call's uid 4252). The callee had been written by
   the **previous step of the same batch** — the whole recipe stays "callee `.vi` files on
   disk, same directory, composed first".
2. **`mcp_call.py` batch mode: a round = one JSON plan + one run.** All six calls of this
   round (ensure → convert ×3 → run ×2) went through one stdio session driven by a single
   plan file, recorded verbatim into a merged transcript
   ([plan](../../research/artifacts/round21/plan.json),
   [transcript](../../research/artifacts/round21/transcript.json)).
3. **G0's `net-unconsumed` check earns its keep.** The first draft of the child VI left the
   iteration shift register's read-back output dangling; `audit_aixml.py` flagged it
   (1W) before anything reached LabVIEW. Wiring it to a `Count` indicator turned the file
   0E/0W and made the two-point check strictly stronger.

## Rebuild + run recipe (no gRPC / Nigel needed)

```bash
# 0) G0 offline gate first — must be green before anything else
python tools/audit_aixml.py --summary "examples/nested-multi-vi-demo/Double It.aixml.xml"
python tools/audit_aixml.py --summary "examples/nested-multi-vi-demo/Sum Of Doubles.aixml.xml"
python tools/audit_aixml.py --summary "examples/nested-multi-vi-demo/Nested Chain Demo.aixml.xml"

# 1) make sure LabVIEW.exe is running (lvai_ensure_labview starts it if not)

# 2) compose callee-first: grandchild, then child, then top (ordering is the rule)
#    — or just run the recorded plan end to end:
python scripts/mcp_call.py --server "C:\path\LabVIEWMCP.exe" batch \
    --plan research/artifacts/round21/plan.json --out transcript.json

# 3) run it (two-point verification)
lvai_run_vi_and_read_values(backend:"pylabview",
    viPath:"<repo>/examples/nested-multi-vi-demo/Nested Chain Demo.vi", inputsJson:'{"N":"3"}')
#   → Sum=12, Count=3
lvai_run_vi_and_read_values(backend:"pylabview",
    viPath:"<repo>/examples/nested-multi-vi-demo/Nested Chain Demo.vi", inputsJson:'{"N":"4"}')
#   → Sum=20, Count=4
```

All three AIXML pass `audit_aixml.py` with **0 errors / 0 warnings** (G0). Evidence
transcripts live in [`research/artifacts/round21/`](../../research/artifacts/round21/)
(`convert-reports.json`, `run-verification.json`, plus the two `*_BDHb.xml` disk
descriptors whose `LinkSaveQualName` entries prove both Call links live in the written
files); the round write-up is
[`research/30-nested-multi-vi-chain.md`](../../research/30-nested-multi-vi-chain.md).

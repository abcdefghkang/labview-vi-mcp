# LabVIEW VI Development via MCP — skill package

A reusable agent skill for building and editing **LabVIEW VI front panels** through LabVIEW MCP servers, with a complete case study: restoring an industrial HMI panel from a single phone photo.

## What's inside

| File | Content |
|---|---|
| `SKILL.md` | Entry point — 10 iron rules, standard loop, delivery habits (English) |
| `references/01-mcp-tools-reference.md` | Both MCP servers (23 + 98 tools), environment setup, CLI fallbacks (Chinese) |
| `references/02-capability-matrix.md` | Verified style names, writable-property matrix, 12 silently-ignored pitfalls, color palette (Chinese) |
| `references/03-workflows-and-verification.md` | Four workflows + copy-paste code templates + troubleshooting table (Chinese) |
| `references/04-case-study-hmi-panel.md` | Photo → HMI panel restoration, full record (Chinese) |
| `references/05-team-sharing-cold-start-and-stdio-drive.md` | Team sharing deck: unattended LabVIEW authoring — cold-start closure (`lvai_ensure_labview`) + no-IDE stdio JSON-RPC drive (`scripts/mcp_call.py`), measured numbers, pitfall list, onboarding checklist (Chinese) |
| `scripts/deliver.py` | Copy master VI + newest render → deliverable + preview PNG |
| `scripts/compare_deliver.py` | Pixel-diff quantification + before/after comparison image |
| `scripts/render_verify.py` | Find newest render / crop & zoom / sample pixel colors |
| `scripts/mcp_call.py` | Minimal MCP stdio driver for LabVIEWMCP.exe — reproduce rounds from a bare shell / CI box without an MCP-capable IDE (pure stdlib) |
| `research/` | 滚动研究看板（`00-status.md`）+ 单轮实证文档：AI 借 MCP 开发 LabVIEW 的完整经验、铁律、闸门与复现入口，Round 1–20 |

## Requirements

- Windows
- LabVIEW 2018 (32-bit) or 2021 (64-bit), with VI Scripting enabled
- **LabVIEW Native MCP** server (open source): <https://github.com/chinayuren2022-2025/labview-native-mcp>
- Optional: a second MCP server exposing `lvai_*` tools (Zuehlke LVAI)
- Python 3.12 bundled with the MCP server (includes Pillow) for the verification scripts

## Install (OpenCode)

```bash
git clone https://github.com/ABCDEFGHKANG/labview-vi-mcp.git ~/.config/opencode/skills/labview-vi-mcp
```

Or drop the folder manually into one of these locations:

```
~/.config/opencode/skills/labview-vi-mcp/     # global, available everywhere
<project>/.opencode/skills/labview-vi-mcp/    # or per project
```

OpenCode discovers `SKILL.md` automatically and loads it when a matching task appears.

## Usage

Ask your agent, for example:

> Add a row of status LEDs to the LabVIEW panel, render it, and verify the result.

## Research (`research/`)

Ongoing measured research on **AI generating LabVIEW code from scratch** (Zuehlke/labview-mcp AIXML pipeline), separate from the panel-beautification skill above:

**Start here:** [`research/00-status.md`](research/00-status.md) — the rolling board: direction (5 lines of work), every round at a glance, what is deliverable vs. conditional vs. impossible today, the numbers, the gates, and the next round's priorities. Updated at the end of every round; the per-round docs below are the evidence behind it.

| Doc | Content |
|---|---|
| `research/00-status.md` | **Board** (Round 23): the 5 research lines, rounds 1–23 table with verdict + commit, capability map in three tiers (deliverable / conditional / impossible), headline metrics, gates G0–G5, priorities P1–P10, current environment and liveness check (Chinese) |
| `research/05-aixml-vi-generation.md` | AIXML format, generation pipeline, dual-backend switching (Chinese) |
| `research/06-best-practices.md` | Reusable methodology: workflow, prompt engineering, review checklist (Chinese) |
| `research/07-measured-session.md` | Round-2 measured session record (Chinese) |
| `research/08-complex-programs.md` | Round-3: complex programs — ShiftReg seed rule, multi-VI Call, `.lvproj` containers (Chinese) |
| `research/09-measured-session-2.md` | Round-3 measured session record incl. bisection table (Chinese) |
| `research/10-state-machine-and-ctl.md` | Round-4: state-machine templating (inline-enum selector, per-frame tunnel duties, SR survival rule), `.ctl` typedefs, VI→AIXML read-back loop (Chinese) |
| `research/11-pylabview-edit-chain.md` | Round-5: pylabview edit chain — read-side uid coordinates + write-side patch loop (AIXML patch / bundle deep-edit / pylv_apply) (Chinese) |
| `research/12-retarget-root-cause.md` | Round-6 (1): retarget run-failure root cause — caller link name must match callee's internal Name; openVI:true recipe; ActiveX shares gRPC process (Chinese) |
| `research/13-state-machine-template-generator.md` | Round-6 (2): state-table → AIXML state-machine generator; single-state blind spot of one-option Case (Chinese) |
| `research/14-array-cluster-node-coverage.md` | Round-6 (3): array (12 nodes) + cluster node coverage; Bundle is append-only (typed-empty base idiom); Split Array unsupported (Chinese) |
| `research/15-bind-pane-typedef-race.md` | Round-7: `lvai_bind_pane_typedef` save-chain vs bind-loop race root cause; one-edge ordering fix; file-level verification as the only trusted verdict (Chinese) |
| `research/16-upstream-tracking-and-event-structures.md` | Round-7 (supplement): upstream v2.0.1→v2.2.0 tracking; cross-validation of our findings vs upstream docs; Event Structure one-call playbook (pylabview); gap census; 5 new iron rules; next-round probes (Chinese) |
| `research/17-complex-program-playbook.md` | Round-8 (offline synthesis): five-gate model for delivering complex programs; loaded-target Call resolution; class method calling its own accessors without a stub; cross-artifact link law (same law as Round-7's race); testing layer rules; workflow economics; 6 new iron rules (Chinese) |
| `research/artifacts/round7/next-probes/` | Round-8 prepared probes: user-event / cluster-payload / two-events / static-events+timeout AIXML (UNVERIFIED, to run when LabVIEW is up) |
| `research/18-v220-capability-delta.md` | Round-9: v2.0.1→v2.2.0 tool-surface delta (106→126, 32 added / 12 gone), the layout engine, `lvai_error_list`, AF override tools, offline indexes; three corrections to our own rules (uid ≥4200, bare-net attributes, `cond` literals); the offline gate G0 and its first audit of our own 50 AIXML (Chinese) |
| `tools/` | Offline gate: vendored upstream linter (37 rules, MIT) + our 16 iron rules as code (LV012/LV013 are backend-aware via `--backend pylabview`; LV014 added in round 13 and it is the rule that unblocked the test layer; LV015 in round 14 refuses a class-method source whose terminals have no `conIdx`; LV016 in round 15 strips AIXML's `\XX` escapes before judging path-ness, so a qualified class target like `Sensor.lvclass\3ATag.vi` stops being mistaken for a path) + merged audit + `lvproj_audit.py`, the only gate that reads a `.lvproj`. `python tools/audit_aixml.py --summary <file>`, ~2.5 s for 60 files, no LabVIEW |
| `research/artifacts/round9/tool-delta.csv` | Every tool added / renamed / dropped between v2.0.1 and HEAD, with the area and the consequence |
| `research/artifacts/round9/lint-sweep-report.md` | First audit of every AIXML this repository ever produced: 21 errors / 92 warnings over 50 documents, with the ledger of which are real, which are negative controls, which are tool blind spots |
| `research/19-cold-build-corpus.md` | Round-10: census of upstream's 25 cold builds (4409 lines) — 57 classes / 193 VIs / 112 tests, and **all 3 failures are deliberate negative controls**; five laws (constant-survival, the class phase is 49 % of cost, boilerplate → generator, status codes lie in both directions, multi-agent constraints); gate G3.5; rules R10-1..7 (Chinese) |
| `research/artifacts/round10/cold-build-census.csv` | All 25 builds as data: date, lines, section titles, final state, error numbers, tools, negative control, lint (blank where the doc does not say — 11 of 25 state a final state) |
| `tools/cold_build_census.py` | The census itself, re-runnable against any upstream checkout; no LabVIEW needed |
| `research/20-first-online-round.md` | Round-11: **the first round with a live LabVIEW**. The real tool surface is 94 `lvai_*` + 5 `pylv_*` over **23 RPCs** (retires round 9's 106→126 count, which came from grepping the exe); four attribute rules measured by live refusals; `timestamp` discard confirmed three ways (document / export / runtime epoch); `helperAixmlInvalid` localised to one file with `backend:"pylabview"` as the working detour; and the inheritance correction — `inheritsFrom` is right, `ancestors[0]` is the trap (Chinese) |
| `research/artifacts/round11/tool-surface-2.0.1.txt` | The 99 tools a live `tools/list` actually advertises — the only trustworthy source for "does this tool exist" |
| `research/artifacts/round11/schema-2.0.1.txt` | gRPC server reflection: 23 rpcs + every message, i.e. what NI's service really offers |
| `research/artifacts/round11/lvclass-parents.json` | 468 classes with their parent resolved offline, `resolvedBy` recorded; 13 parents turn out to be interfaces |
| `research/23-lvoop-and-the-wrong-installation.md` | Round-14: **the whole LVOOP chain, and one wrongly chosen screw**. (1) On a dual-install machine pylabview resolves against the WRONG LabVIEW: `resolve.labview_root()` returned **LabVIEW 2018** while 2026 was running, because it takes the first hit walking the x86 base first - so `Add Class.lvlib` / `Add Interface.lvlib` (which live under `resource\Framework\Providers`) read as "not in the installation". One-line fix, effective immediately (the scripts are read off disk per step, no restart). (2) `panePattern 4815` does NOT rescue a terminal without `conIdx`: same call, `Scale By.vi` (conIdx 0/1/2) fine, `Reset.vi` (none) dies at `no <cons> array in the front-panel heap` and never becomes a member - which also settles round 10's "empty cons array": an empty `<cons>` and no pane are the same fact. (3) A class implementing an interface without the override is broken, and the error never says so: `execState 0` before, `1` after adding only that override, with the same generic "error of type 8 / full development system" text round 6 saw for a different cause. (4) Project entries the class tools write are destroyed by LabVIEW's own save of a stale in-memory copy, and `create_accessors` then reports it as a path mismatch. (5) `ancestors` puts interfaces BEFORE the real parent class; accessor names follow the IDE language (`读取Name.vi`); `vi_terminals` mangles non-ASCII terminal names. Built: interface + method + 2 classes + 4 accessors, all verified from the files |
| `research/artifacts/round14/Lvoop Demo.lvproj` | 4 classes, every entry present, `lvproj_audit.py` clean |
| `research/artifacts/round14/sensor-reset-noconex.aixml.xml` | The A/B negative fixture (no `conIdx`); `sensor-scale-by.aixml.xml` is the same shape that works |
| `research/artifacts/round14/lib/` | `Can Scale.lvclass` (interface) + its method, `Sensor.lvclass` + override, `Temp Sensor.lvclass` (child), `No Override.lvclass` (the broken-then-fixed probe), 4 wizard accessors |
| `tools/lvproj_audit.py` | Entry-vs-file reconciliation for a `.lvproj`; catches the deleted-entry shape, has a negative control |
| `research/24-the-2018-station.md` | Round-15: **the 2018 station, and one version warning struck down**. The machine switched to LabVIEW 2018 (32-bit) with no Nigel, so the whole gRPC route is dead — and yet the AIXML → VI → run pipeline works end to end on pylabview, with 2026-stamped VIs opened **and executed** by 2018 (`y = x·factor`, 6×7 → 42.00000000000000), striking down the server's own versionWarning ("2018 refuses, Error 1125"). On that basis the LVOOP chain (dynamic method + static member + class constant + caller) runs end to end on 2018, and P15 is nailed down: **binding happens at edit time, traced along dataflow, and a static "type washer" cannot stop it** — three probes (direct / dynamic-method cascade / static anchor) plus binary evidence. Plus the no-gRPC tool-surface truth table, the Class-constant recipe as the only correct way to write a class caller, and LV016 (Chinese) |
| `research/25-grpc-route-restored.md` | Round-16: **gRPC route restored on a 2026-capable station**. Full author(grpc)→compile(grpc)→run(pylabview) loop proven (y=42); three new tool/env rules LV017/018/019; the orphan p16 LVOOP tree validated as a legal 2026 Chinese project; `dump_schema` authoritative 23-RPC face (Chinese) |
| `research/26-complex-demo-showcase.md` | Round-17: **gRPC can be down and the loop still runs** (pylabview-only closure) + **LV020 loop-dialect boundary rule nailed**. First truly machine-verified "complex program" flagship — `examples/complex-demo/Accumulator.vi` (While Loop + 4 shift registers, Sum/SumSq/Product), verified at N=3 and N=5; the `traffic-light.aixml.xml` loop sample was never actually compiled and carried a boundary bug (Chinese) |
| `research/artifacts/round15/p15/` | The self-contained LVOOP tree this round ran: `Can Scale` interface + `Sensor` / `Temp Sensor` classes + `Tag` dynamic method ×2 + `Carrier` static member + three dispatch probes + exported AIXML evidence, with the whole tree still verifying `execState 1` |
| `research/artifacts/round15/scratch/` | The 2018 run probes: `probe-scale-by.vi` and `probe-arith.vi` — the two VIs that struck down the version warning |
| `research/22-connector-pane-the-missing-slot.md` | Round-13: **the missing slot**. `connection` says required/recommended/optional; only `conIdx` puts a terminal ON the connector pane, and with no `conIdx` the composer writes `conNum=-1` and leaves the skeleton's `objFlags 0x10000` alone — that flag's own comment reads "NO TERMINAL ON THE PANE". Measured four ways on one VI (A: no `conIdx` → 0 in/0 out; B: 0/1/2 → pane; C: out of document order → **slots follow `conIdx`, not document order**; D: only `x` → a PARTIAL pane, which is legal). End to end: `3*5 → Result=15`. **A Call to a pane-less VI composes, runs and reports no error while passing nothing** (`Marker Out=99`). `generate_test` goes `noTerminals` → `route:"direct"` → `no Test.lvclass`, i.e. Caraya is simply not installed on this station (VIPM holds only `.spec` caches). With no framework available, a 20-node self-contained test was written instead: positive `AllPass=true / Error=0`, negative `false / 1`. Also captures a real crash: 5× `Fatal insanity (0x00000004)` in `lvai_typedef_tree.vi`, `fpsane.cpp(1140)`, 4 minidumps, all inside `ConvertAIXMLToVI.vi`. Corpus: 383 terminals, **9.9% carry a `conIdx`** |
| `research/artifacts/round13/conidx-probe-{a,b,c,d}.aixml.xml` | The four-way pane experiment; `make_probes.py` generates all four and they differ only in `conIdx` |
| `research/artifacts/round13/selfcheck-test.aixml.xml` | Framework-free test: 3 Calls, 3 Subtracts, 2 Adds, 1 `Equal?`. Note the terminal spelling **`x = y?`**, spaces included |
| `research/artifacts/round13/out/Selfcheck Conpane Probe B.vi` | `AllPass=true`, `Total Error=0`; its negative control answers `false` / `1` |
| `research/artifacts/round13/out/_labview-crash-16-55.txt` | The crash transcript. LabVIEW rewrites that log on every start, so it had to be captured before `lvai_ensure_labview` ran — this is why it is a transcript and not a copy |
| `research/21-first-panel-and-boundary-round.md` | Round-12: **boundaries, event timeouts, and panel-preserving grafts**. (1) a net may not cross a structure border implicitly — the rule our gate was missing, now LV012, and it is why the round-7 probe had never converted; (2) the two composers disagree: on the same file NI's converter answers `errorCode 0` and turns 43 declared tunnels into 154, pylabview refuses; (3) an Event Structure's frames and registration **do** survive (3 EventSpecs, Timeout included) but the `eventTimeOut` terminal has no AIXML spelling, so a ` Timeout ` frame never fires — `Timeouts=0` over 2.2 s with 500 ms wanted, no error (LV013); (4) `lvai_graft_diagram` works **only on pylabview** here and the grafted panel+program runs correctly (`Sum=12/Average=4/Stop`); (5) four of the 78 helper documents are rejected on this station, which is what kills `signalsJson`, `connector_pane` and `graft(grpc)`; (6) the test layer is blocked at `noTerminals` (Chinese) |
| `research/artifacts/round12/p5-valuechange-timeout-frames-v2.aixml.xml` | The round-7 probe after the boundary fix: `execState 1`. With the original it forms the regression pair for LV012 — 6 errors vs 1 |
| `research/artifacts/round12/panel-supplied.aixml.xml` | A **panel-only** VI (7 terminals, 0 nodes) — what a graft needs on the input side, and what `Batch Averager Empty.vi` turned out not to be |
| `research/artifacts/round12/out/Grafted Scaled.vi` | Supplied panel + generated diagram + one new control, verified by running it |
| `research/artifacts/round12/lint-sweep.json` | The same 64 documents under both backends: 26E/269W (grpc semantics) vs 187E/108W (pylabview) |
| `tools/lvclass_parent_scan.py` | Offline parent/interface scanner for `.lvclass`; the three URL conventions it had to learn are in the docstring |
| `research/artifacts/` | Generated VIs + AIXML sources per round |
| `research/examples/` | Copy-ready AIXML snippets and a debug playbook |
| `examples/complex-demo/` | **Flagship runnable example** — `Accumulator.aixml.xml` (AI-authored) + compiled `Accumulator.vi` + `README.md`: a While Loop with 4 shift registers accumulating Sum/SumSq/Product over N iterations; verified at N=3 and N=5; rebuild + run recipe for the pylabview backend (no gRPC/Nigel needed) |
| `research/29-multi-vi-orchestration-pylabview.md` | Round-20: **multi-VI orchestration closed (P6) + unattended cold-start closure**. Top-level VI Calls two subVIs (While-Loop iterator + Divide aggregator), two-point run verification bit-for-bit (N=5 → 15/5/3.0, N=3 → 6/3/2.0); **the pylabview composer resolves Call targets from the callee FILE on disk, not IDE memory** (round-6's `openVI:true` belongs to the gRPC route; ordering is the rule); `lvai_ensure_labview` cold-starts LabVIEW itself; upstream survey: v2.3.1 shipped `lvai_layout_diagram`/`lvai_error_list` (114 tools), class-specifier constants still absent (Chinese) |
| `examples/multi-vi-demo/` | **Multi-VI program** — top-level `Multi VI Demo.vi` orchestrating `Accumulate N.vi` (While Loop + 2 shift registers) and `Mean Of Pair.vi` (Divide, int→DBL promotion across the pane); 3 AIXML + 3 compiled `.vi` + README with the rebuild-and-run recipe; evidence in `research/artifacts/round20/` |
| `research/30-nested-multi-vi-chain.md` | Round-21: **nested multi-VI chain + batch drive finalized**. Three-level Call chain — top → child (a Call INSIDE a While Loop accumulating the grandchild's output) → grandchild (one Multiply); two-point run bit-for-bit (N=3 → Sum 12 / Count 3, N=4 → 20/4, Sum crosses 4 pane boundaries); the R6/R20 recipe applies unchanged — **no new dialect for Calls inside structures or at depth**. `scripts/mcp_call.py` gains `batch` mode: a round = one JSON plan + one run, idempotent and re-runnable (~5 s); G0's `net-unconsumed` rule caught a dangling shift-register output on first contact (Chinese) |
| `examples/nested-multi-vi-demo/` | **Three-level nested chain** — `Nested Chain Demo.vi` → `Sum Of Doubles.vi` (While Loop + 2 SR + in-loop Call) → `Double It.vi`; 3 AIXML + 3 compiled `.vi` + README; evidence in `research/artifacts/round21/` (plan + transcript pair is the recorded, re-runnable round) |
| `research/31-caraya-testing-layer.md` | Round-22: **Caraya installed by hand, the test layer's last link closed (P2/P7)**. The "missing piece" verdict is corrected — the three Caraya tools were always in the 99-tool surface, only the runtime was absent. `.vip` = zip, installed from `vipm-io/caraya` 2.0.0 (728 files, one nesting-detour on the way); full loop `generate_test` → `generate_caraya_test_runner` → `run_caraya_tests` on pylabview; positive 3/0, negative control (one `lvai_set_constant` edit) failures=1 **naming the exact case**, restore to green — verdicts all read off the on-disk JUnit report (Chinese) |
| `examples/caraya-demo/` | **AI-written, AI-judged Caraya suite** — `Test Double It.vi` + `run-tests.vi` (both tool-generated) + `TestReport.xml`; evidence in `research/artifacts/round22/` (2 batch plans + transcripts + install notes) |
| `research/32-mcp-upgrade-v2.3.1.md` | Round-23: **labview-mcp upgraded v2.0.1 → v2.3.1 with zero migration (P3)**. Release zip is the install layout (stop exe → rename old dir → extract); the upstream **still ships the `labview_root()` first-hit bug** R14 found (208→657-line rewrite didn't fix it) — patch re-applied by hand, diff archived; 114 tools confirmed, R22 Caraya suite replays green (Chinese) |
| `research/artifacts/round23/` | Upgrade evidence: full 114-tool surface JSON (475 KB), the re-applied `resolve.py` patch as `.diff`, upgrade notes, post-upgrade regression plan + transcript |

## Notes

- Paths like `C:\Users\<you>` and `C:\LV_AUTOTEST\...` in the docs and scripts are examples — adapt them to your machine before use.
- All "silently ignored / no effect" findings were verified on LabVIEW 2018 (32-bit) via capability probes; behavior may differ on other versions — probe first.

## License

MIT — see `LICENSE`.

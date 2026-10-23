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
| `scripts/deliver.py` | Copy master VI + newest render → deliverable + preview PNG |
| `scripts/compare_deliver.py` | Pixel-diff quantification + before/after comparison image |
| `scripts/render_verify.py` | Find newest render / crop & zoom / sample pixel colors |

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

| Doc | Content |
|---|---|
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
| `tools/` | Offline gate: vendored upstream linter (37 rules, MIT) + our 12 iron rules as code (LV012/LV013 added in round 12, and they are backend-aware: `--backend pylabview`) + merged audit. `python tools/audit_aixml.py --summary <file>`, ~2.5 s for 60 files, no LabVIEW |
| `research/artifacts/round9/tool-delta.csv` | Every tool added / renamed / dropped between v2.0.1 and HEAD, with the area and the consequence |
| `research/artifacts/round9/lint-sweep-report.md` | First audit of every AIXML this repository ever produced: 21 errors / 92 warnings over 50 documents, with the ledger of which are real, which are negative controls, which are tool blind spots |
| `research/19-cold-build-corpus.md` | Round-10: census of upstream's 25 cold builds (4409 lines) — 57 classes / 193 VIs / 112 tests, and **all 3 failures are deliberate negative controls**; five laws (constant-survival, the class phase is 49 % of cost, boilerplate → generator, status codes lie in both directions, multi-agent constraints); gate G3.5; rules R10-1..7 (Chinese) |
| `research/artifacts/round10/cold-build-census.csv` | All 25 builds as data: date, lines, section titles, final state, error numbers, tools, negative control, lint (blank where the doc does not say — 11 of 25 state a final state) |
| `tools/cold_build_census.py` | The census itself, re-runnable against any upstream checkout; no LabVIEW needed |
| `research/20-first-online-round.md` | Round-11: **the first round with a live LabVIEW**. The real tool surface is 94 `lvai_*` + 5 `pylv_*` over **23 RPCs** (retires round 9's 106→126 count, which came from grepping the exe); four attribute rules measured by live refusals; `timestamp` discard confirmed three ways (document / export / runtime epoch); `helperAixmlInvalid` localised to one file with `backend:"pylabview"` as the working detour; and the inheritance correction — `inheritsFrom` is right, `ancestors[0]` is the trap (Chinese) |
| `research/artifacts/round11/tool-surface-2.0.1.txt` | The 99 tools a live `tools/list` actually advertises — the only trustworthy source for "does this tool exist" |
| `research/artifacts/round11/schema-2.0.1.txt` | gRPC server reflection: 23 rpcs + every message, i.e. what NI's service really offers |
| `research/artifacts/round11/lvclass-parents.json` | 468 classes with their parent resolved offline, `resolvedBy` recorded; 13 parents turn out to be interfaces |
| `research/21-first-panel-and-boundary-round.md` | Round-12: **boundaries, event timeouts, and panel-preserving grafts**. (1) a net may not cross a structure border implicitly — the rule our gate was missing, now LV012, and it is why the round-7 probe had never converted; (2) the two composers disagree: on the same file NI's converter answers `errorCode 0` and turns 43 declared tunnels into 154, pylabview refuses; (3) an Event Structure's frames and registration **do** survive (3 EventSpecs, Timeout included) but the `eventTimeOut` terminal has no AIXML spelling, so a ` Timeout ` frame never fires — `Timeouts=0` over 2.2 s with 500 ms wanted, no error (LV013); (4) `lvai_graft_diagram` works **only on pylabview** here and the grafted panel+program runs correctly (`Sum=12/Average=4/Stop`); (5) four of the 78 helper documents are rejected on this station, which is what kills `signalsJson`, `connector_pane` and `graft(grpc)`; (6) the test layer is blocked at `noTerminals` (Chinese) |
| `research/artifacts/round12/p5-valuechange-timeout-frames-v2.aixml.xml` | The round-7 probe after the boundary fix: `execState 1`. With the original it forms the regression pair for LV012 — 6 errors vs 1 |
| `research/artifacts/round12/panel-supplied.aixml.xml` | A **panel-only** VI (7 terminals, 0 nodes) — what a graft needs on the input side, and what `Batch Averager Empty.vi` turned out not to be |
| `research/artifacts/round12/out/Grafted Scaled.vi` | Supplied panel + generated diagram + one new control, verified by running it |
| `research/artifacts/round12/lint-sweep.json` | The same 64 documents under both backends: 26E/269W (grpc semantics) vs 187E/108W (pylabview) |
| `tools/lvclass_parent_scan.py` | Offline parent/interface scanner for `.lvclass`; the three URL conventions it had to learn are in the docstring |
| `research/artifacts/` | Generated VIs + AIXML sources per round |
| `research/examples/` | Copy-ready AIXML snippets and a debug playbook |

## Notes

- Paths like `C:\Users\<you>` and `C:\LV_AUTOTEST\...` in the docs and scripts are examples — adapt them to your machine before use.
- All "silently ignored / no effect" findings were verified on LabVIEW 2018 (32-bit) via capability probes; behavior may differ on other versions — probe first.

## License

MIT — see `LICENSE`.

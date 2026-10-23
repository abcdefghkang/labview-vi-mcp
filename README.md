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
| `research/artifacts/round8/probe-recipes.md` | Round-8 probe recipes P6-P9: class-method self-accessor chain / interface override save-order A-B / Caraya minimal suite / cold-start recheck (UNVERIFIED) |
| `research/artifacts/` | Generated VIs + AIXML sources per round |
| `research/examples/` | Copy-ready AIXML snippets and a debug playbook |

## Notes

- Paths like `C:\Users\<you>` and `C:\LV_AUTOTEST\...` in the docs and scripts are examples — adapt them to your machine before use.
- All "silently ignored / no effect" findings were verified on LabVIEW 2018 (32-bit) via capability probes; behavior may differ on other versions — probe first.

## License

MIT — see `LICENSE`.

---
name: LabVIEW VI Development via MCP
description: Build and modify LabVIEW VI front panels through MCP tooling — create controls, decorations, text labels, LEDs and charts; batch-edit object properties; render the panel to PNG and verify at pixel level; restore HMI panels from photos or screenshots; quantify visual change with pixel diffs. Use whenever a task involves LabVIEW, VI front panels, HMI restoration, or tools such as add_object, set_property, render_vi, and lvai_*.
---

# LabVIEW VI Development via MCP

Work with LabVIEW through two MCP servers (names may differ on your machine):

| Server | Backend | Role |
|---|---|---|
| `labview-native-2018` | COM / VI Scripting (LabVIEW 2018 32-bit) | **Primary** — pixel-level front-panel editing (23 tools). Open source: `github.com/chinayuren2022-2025/labview-native-mcp` |
| `labview` | Zuehlke LVAI (LabVIEW 2026) | **Secondary** — generate / describe / test / classes (98+ `lvai_*` tools) |

## Read next (references/)

| Goal | File |
|---|---|
| Tool semantics, environment paths, CLI fallbacks | `references/01-mcp-tools-reference.md` |
| Writable vs silently-ignored properties (the pitfall list) | `references/02-capability-matrix.md` |
| Workflow templates + verification scripts | `references/03-workflows-and-verification.md` |
| Case study: photo → industrial HMI panel restoration | `references/04-case-study-hmi-panel.md` |

(Reference files are written in Chinese — the rules below cover the critical content in English.)

## The 10 iron rules

1. `set_property` values must be **strings**; `add_object` returns `{result:N}` (the object reference); position with `location:[x,y]` (`bounds` is ignored).
2. Decoration sizing uses `Size:Width` / `Size:Height`; `Bounds:Area` width/height has **no effect**.
3. New objects always render on top; `Position` writes never change Z-order → draw in creation order: backgrounds → pipes/graphics → text.
4. Boolean captions render **above** the button and cannot be moved or hidden (`Position`/`Visible` writes are silently ignored; `FontSize` is unreliable). `Position:Top` means the top of the caption+button bounding box; the button itself renders ~12–15 px lower ⇒ always reserve space above for captions.
5. Classic LEDs light red; modern LEDs (21012/21013) light green and their color cannot be customized; Boolean `Colors[4]` writes don't stick.
6. Colors are **decimal** strings of `0x00RRGGBB`; transparent 16777216 makes text fully invisible.
7. `set_property` succeeding ≠ visually applied (see rule 4) ⇒ after key changes, always `save_vi` + `render_vi` and inspect the PNG.
8. `edit_batch` stops at the first failure — no rollback, no autosave; for bulk edits, loop in code mode with a per-step try/catch and collect the failure list (template in references/03).
9. Renders land under `<LabVIEWNativeMCP>\work\mcp_render\<VI>\export_*\*p.png` — take the **newest by mtime**; render pixel coordinates ≈ front-panel coordinates (1:1).
10. Git Bash mangles Chinese paths/heredocs ⇒ write `.py` files with a file tool and run them with the bundled Python (includes Pillow): `PYTHONIOENCODING=utf-8 "%LOCALAPPDATA%\LabVIEWNativeMCP\runtime\python.exe" script.py`.

## Standard loop

```
new/open → add_object → set_property → inspect_vi for fresh references → delete_objects for cleanup
→ save_vi → render_vi(surface:"panel") → crop & zoom pixel verification → fix
→ deliver (copy VI + refresh preview + pixel-diff report)
```

## Capability probe

For any property or style you are unsure about: test it on a scratch VI first, read it back + render, and only then apply it to the main VI. Every "silently ignored" conclusion in this skill came from such probes.

## Delivery habits

- Every delivery must be **visible** and **quantified**: report the changed-pixel count and percentage, plus a stacked before/after comparison image with red diff overlays.
- A ~200 px change is invisible to the eye; ~90,000 px (~6 %) reads as an obvious change.

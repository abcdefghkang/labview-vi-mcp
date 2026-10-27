# Complex Demo — `Accumulator.vi`

A genuinely *algorithmic* LabVIEW program, authored entirely from AIXML by an AI and
verified to run. It is the project's flagship "complex program" showcase: a **While Loop
with four shift registers** that, over `N` iterations, accumulates the running **Sum**,
**Sum of Squares**, and **Product** of the integers `1..N`.

This example proves the project's core claim — *AI can directly develop a non-trivial
LabVIEW program* — using only the **pylabview backend** (no gRPC / Nigel AI service
required; a plain running `LabVIEW.exe` is enough for the run step).

---

## What it does

| Input | Type | Meaning |
|---|---|---|
| `N` | I32 (control) | Number of iterations; element at iteration *k* (0-based) is `k+1`. |

| Output | Type | Formula (over elements 1..N) |
|---|---|---|
| `Sum` | I32 | Σ element |
| `SumSq` | I32 | Σ element² |
| `Product` | I32 | Π element |
| `Done` | Boolean | `true` once the loop terminates. |

Verified results:

| N | Sum | SumSq | Product |
|---|---|---|---|
| 3 | 6  | 14 | 6   |
| 5 | 15 | 55 | 120 |

(hand-computed: N=5 → 1+2+3+4+5 = 15; 1+4+9+16+25 = 55; 1·2·3·4·5 = 120.)

---

## Block diagram (concept)

```
        N ──┐
            ├──[Tunnel In1]──> max
   Zero ────┐│                (loop init for 3 shift registers)
   One  ──┐ │├──[Tunnel In2]──> one
         │ ││
   ┌─────▼─▼─▼────────── While Loop ──────────────────────┐
   │  ShiftReg iter   : Left=Zero  →  iter                │
   │  ShiftReg sum    : Left=Zero  →  sum                 │
   │  ShiftReg sq     : Left=Zero  →  sq                  │
   │  ShiftReg product: Left=One   →  product             │
   │                                                       │
   │  iter1  = Add(iter, one)                               │
   │  sum    = Add(sum, iter1)        (next shift register) │
   │  e2     = Multiply(iter1, iter1)                       │
   │  sq     = Add(sq, e2)                                  │
   │  product= Multiply(product, iter1)                     │
   │  stop?  = GreaterOrEqual(iter1, max)                   │
   │  Condition(stop)  ── loop exit                         │
   └───────────────────────────────────────────────────────┘
        │
   Sum ──┘  SumSq ──┘  Product ──┘  (shift-register Right → indicators)
   Done ← True (root constant)
```

The four shift registers are the loop's memory; the `Condition` node terminates the loop
once `iter1 >= N`.

---

## How to rebuild and run

You need the `labview-mcp` MCP server connected (the `labview` entry in `mcp.json`).
The gRPC / Nigel AI service does **not** need to be running — this example uses the
pylabview backend.

```bash
# 1) Author the .vi from AIXML using pylabview's own composer (no gRPC needed)
lvai_convert_aixml_to_vi(
    backend: "pylabview",
    aiXmlFilePath: "<repo>/examples/complex-demo/Accumulator.aixml.xml",
    viPath:        "<repo>/examples/complex-demo/Accumulator.vi")

# 2) Run it over LabVIEW's ActiveX server (LabVIEW.exe must be running)
lvai_run_vi_and_read_values(
    backend:   "pylabview",
    viPath:    "<repo>/examples/complex-demo/Accumulator.vi",
    inputsJson: '{"N":"5"}')
# → Sum=15, SumSq=55, Product=120, Done=true
```

`Accumulator.vi` is committed in this folder, so it is runnable as-is without step 1.

---

## Authoring rules this example pins down (Round 17 / LV020)

The loop dialect below was **never actually compiled** before this example — the
`traffic-light.aixml.xml` reference in `research/artifacts/round16` was written in an
offline round and silently carried a boundary bug. The pylabview composer enforces a hard
rule that the earlier AIXML did not respect:

> **LV020 — A net may not cross a loop boundary without a Tunnel.**
> - A **constant that feeds a loop-internal node** must enter the loop through a `Tunnel`
>   (`<Tunnel _id="InN" inputs="value:<root net>" outputs="value:<inside net>"/>`).
> - A **constant that feeds a shift-register terminal** (which sits *on* the loop boundary)
>   must live on the **root diagram** and wire straight into the `Left` terminal — do **not**
>   place it inside the loop, or the composer rejects it with
>   *"net '…' crosses a diagram boundary without a tunnel"*.
> - A shift register's `Right` terminal (the loop's output) feeding a root-level indicator
>   is the *exempted* crossing and is allowed.

In this file: `Zero`/`One` stay on the root (they seed the shift-register `Left`s, and
`One` additionally enters via `Tunnel In2` to reach the in-loop `Add`); `N` enters via
`Tunnel In1`; only `True` (for `Done`) is a pure root→root wiring.

Other rules observed: every terminal carries `conIdx` (so the VI is Callable, LV014);
all authored `uid`s are ≥ 4200 (LV009); the `Condition` node carries `value="stop"`; the
While Loop element is `<Structure _name="While Loop" count="">`.

See `research/26-complex-demo-showcase.md` for the full write-up and the minimal
`loop-probe` dialect-validation VI used to derive LV020.

#!/usr/bin/env python3
"""audit_aixml.py - one offline gate over many AIXML files.

Runs the two checkers and merges their findings, so a build can ask one question
before spending a LabVIEW round trip:

    python audit_aixml.py research/artifacts/**/*.xml
    python audit_aixml.py --markdown --out report.md --root research/artifacts .
    python audit_aixml.py --summary research/artifacts

  tools/aixml_lint.py   37 rules, vendored upstream (MIT) - parenting, nets,
                        uids, type grammar, VI Server names
  tools/lvrule_check.py 8 rules of our own - binary rules of rounds 1-9 that no
                        upstream check knows

Exit code 1 when either checker reports an error in any file.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINT = os.path.join(HERE, "aixml_lint.py")
RULES = os.path.join(HERE, "lvrule_check.py")

SEV_ORDER = {"error": 0, "warning": 1, "info": 2}

#: Findings we have measured to be FALSE POSITIVES, suppressed by name here and
#: counted separately, so a report never quietly loses them.
#:
#: `cond="true"` / `cond="false"` on a Tunnel is a LITERAL, not a net. Round 4
#: wrote stop tunnels exactly that way and LabVIEW/NI's converter accepted them,
#: exported them and ran them (research/artifacts/round4, the state machine and
#: its `ref-...-exported` twin). The vendored linter lists `cond` as CONSUMING a
#: bare net (BARE_NET_ATTRS) with no exception for the two literal spellings, so
#: it reports `net "true" is read ... but no element writes it` - 7 errors over 4
#: files of ours. Reported upstream as a blind spot; suppressed here until a
#: refreshed copy carries the literals.
FP_CONDS = ("true", "false")


def is_known_false_positive(f):
    msg = f.get("message") or ""
    if f.get("check") in ("net-unproduced", "net-unconsumed"):
        return any(f'net "{c}"' in msg for c in FP_CONDS)
    return False


def document_kind(path):
    """Only <VI> is an AIXML document. <RSRC>/<FPHb> are pylabview dumps."""
    import xml.etree.ElementTree as ET
    try:
        for _, el in ET.iterparse(path, events=("start",)):
            return "aixml" if el.tag == "VI" else "other"
    except Exception:
        return "unparseable"
    return "empty"


def run_many(script, paths):
    """One process per checker, not one per file: the linter loads its VI Server
    catalogue on start-up, so a per-file spawn costs ~1.3 s of every call."""
    p = subprocess.run([sys.executable, script, "--json", *paths],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        msg = (p.stderr or p.stdout or "no output").strip()[:400]
        return {path: [{"severity": "error", "check": "audit-crashed", "uid": "-",
                        "element": os.path.basename(script), "path": "", "message": msg}]
                for path in paths}
    return {entry["file"]: entry["findings"] for entry in data.get("files", [])}


def audit(paths):
    lint = run_many(LINT, paths)
    ours = run_many(RULES, paths)
    out = []
    for path in paths:
        raw = lint.get(path, []) + ours.get(path, [])
        suppressed = [f for f in raw if is_known_false_positive(f)]
        merged = [f for f in raw if not is_known_false_positive(f)]
        merged.sort(key=lambda f: (SEV_ORDER.get(f["severity"], 3), f["check"]))
        entry = {"file": path, "findings": merged, "kind": document_kind(path)}
        if suppressed:
            entry["suppressed"] = suppressed
        out.append(entry)
    return out


def summarise(results):
    """Counts over AIXML documents only; dumps are reported apart."""
    by_code, sev = {}, {"error": 0, "warning": 0, "info": 0}
    for r in results:
        if r.get("kind") != "aixml":
            continue
        for f in r["findings"]:
            sev[f["severity"]] = sev.get(f["severity"], 0) + 1
            by_code[f["check"]] = by_code.get(f["check"], 0) + 1
    return sev, dict(sorted(by_code.items(), key=lambda kv: -kv[1]))


def main(argv):
    # allow_abbrev=False is NOT cosmetic: `--json` used to abbreviate to
    # `--json-out`, so `audit_aixml.py --json <file>` swallowed the FIRST PATH as
    # the report's destination and OVERWROTE that AIXML with 2,889 lines of JSON.
    # Measured 2026-10-23 on research/artifacts/round10/lv009-probe.aixml.xml;
    # recovered from git, and the trap is closed here.
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("paths", nargs="+", help="files, directories or globs")
    ap.add_argument("--markdown", action="store_true", help="report as markdown tables")
    ap.add_argument("--out", help="write the report to this file")
    ap.add_argument("--summary", action="store_true", help="counts only")
    ap.add_argument("--json-out", help="write the full findings, messages included, as JSON")
    ap.add_argument("--root", default=".", help="strip this prefix from paths in the report")
    args = ap.parse_args(argv)

    files = []
    for p in args.paths:
        if os.path.isdir(p):
            files += glob.glob(os.path.join(p, "**", "*.xml"), recursive=True)
        elif any(ch in p for ch in "*?"):
            files += glob.glob(p, recursive=True)
        else:
            files.append(p)
    files = sorted(set(files))
    if not files:
        print("no XML files found", file=sys.stderr)
        return 2
    # A report written ON TOP of an input is always a mistake, never an intent.
    for dest in (args.out, args.json_out):
        if dest and os.path.abspath(dest) in {os.path.abspath(f) for f in files}:
            print(f"refusing to overwrite input document '{dest}' with a report", file=sys.stderr)
            return 2

    results = audit(files)
    sev, by_code = summarise(results)
    rel = [{"file": os.path.relpath(r["file"], args.root).replace("\\", "/"),
            "findings": r["findings"], "kind": r.get("kind"),
            "suppressed": len(r.get("suppressed") or [])} for r in results]
    aixml = [r for r in rel if r["kind"] == "aixml"]
    other = [r for r in rel if r["kind"] != "aixml"]
    dirty = [r for r in aixml if r["findings"]]
    suppressed_total = sum(r["suppressed"] for r in rel)

    lines = []
    tail = (f"{len(aixml)} AIXML document(s), {len(dirty)} with findings: "
            f"{sev['error']} error(s), {sev['warning']} warning(s), {sev['info']} info")
    if other:
        tail += f"; {len(other)} non-AIXML file(s) skipped (RSRC/FPHb dumps)"
    if suppressed_total:
        tail += f"; {suppressed_total} known false positive(s) suppressed (cond=\"true\"/\"false\")"
    if args.markdown:
        lines.append("| file | errors | warnings | codes |")
        lines.append("|---|---:|---:|---|")
        for r in aixml:
            if not r["findings"]:
                continue
            e = sum(1 for f in r["findings"] if f["severity"] == "error")
            w = sum(1 for f in r["findings"] if f["severity"] == "warning")
            codes = ", ".join(sorted({f["check"] for f in r["findings"]}))
            lines.append(f"| `{r['file']}` | {e} | {w} | {codes} |")
        lines.append("")
        lines.append("| code | count |")
        lines.append("|---|---:|")
        for code, n in by_code.items():
            lines.append(f"| `{code}` | {n} |")
        lines.append("")
        lines.append(f"**{tail}.**")
    else:
        for r in aixml:
            if not r["findings"]:
                continue
            e = sum(1 for f in r["findings"] if f["severity"] == "error")
            w = sum(1 for f in r["findings"] if f["severity"] == "warning")
            lines.append(f"{r['file']}  [{e}E/{w}W]")
            if not args.summary:
                for f in r["findings"]:
                    lines.append(f"   {f['severity'][:4].upper()} {f['check']:<28} "
                                 f"uid={f['uid']:<6} {f['element']}")
        lines.append("")
        lines.append(tail)
        if not args.summary:
            lines.append("by code: " + ", ".join(f"{c}={n}" for c, n in by_code.items()))

    text = "\n".join(lines)
    print(text)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"summary": {"files": len(aixml), "withFindings": len(dirty),
                                   "skippedNonAixml": len(other),
                                   "suppressed": suppressed_total, **sev},
                       "byCode": by_code,
                       "files": aixml},
                      fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        print(f"json written to {args.json_out}", file=sys.stderr)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
        print(f"\nwritten to {args.out}", file=sys.stderr)
    return 1 if sev["error"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

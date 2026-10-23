#!/usr/bin/env python3
"""lvrule_check.py - the iron rules of this research, as an offline gate.

`tools/aixml_lint.py` (vendored upstream) covers what upstream learned without
LabVIEW: parenting, nets, uids, type grammar, VI Server names. It knows nothing
about what WE measured in rounds 1-8, because those facts were only ever written
into prose (`research/06-best-practices.md`, `research/15`, `research/17`). This
script is that prose turned into checks, so an AI can find the fault before it
spends a LabVIEW round trip on it.

    python lvrule_check.py <file.xml> [...]      human readable
    python lvrule_check.py --json <file.xml>     machine readable

Exit code 1 when at least one finding is an error, 0 otherwise.

The rules, and the round that paid for each one:

  LV001  no XML comments in AIXML ......................... round 7
         A comment before <VI> yields an EMPTY diagram with errorCode 0 (the
         silent kind of failure); between children it is Error 42. Nothing in
         the answer says "comment", so it reads as a composer bug.

  LV002  RETIRED 2026-10-23 - upstream `uid-low` covers it  ... round 9
         Our own rule said "uid >= 100", taken from the 10-35 range LabVIEW
         overwrites. The ceiling is not 42 and it moves with the panel heap
         (42..163 observed over 132 blocks), so 100 is inside it on a long
         session; upstream settled 4200 by A/B with a control, and its linter
         already reports every uid below it. Re-implementing it here only
         doubled every warning, so the check is gone and the CORRECTION lives
         in prose: research/18-v220-capability-delta.md §4 and
         research/06-best-practices.md. Number kept, never reused.

  LV003  a shift register's seed is produced at root ....... round 3 (A-E), round 4
         `Left inputs` reading a net that is produced INSIDE the same loop is
         the "wire forms a cycle" false report: the seed must be a root-level
         value carried across the border. Two of five arms failed exactly here.

  LV004  a Case Structure has more than one frame ...... round 8
         A single-selector Case (one frame) is written as a valid document and
         then runs state 0: the composer emits an empty tunnel stub. Straight
         line logic is the fix, not a second selector value.

  LV005  a While Loop carries a Condition ................. round 4
         Without one the loop cannot be stopped from the diagram and LabVIEW
         runs it forever; the document still validates.

  LV006  a Call target is a name, not a path ............... round 6
         A path never resolves: the link is by NAME against what the
         installation or the loaded project can find. The failure surfaces as
         Error 53 at convert, or as a caller that only recompiles with the full
         development system.

  LV007  a ShiftReg has both a Left and a Right .......... round 4
  LV008  a Case Structure's frames have distinct selectors . round 4
         Two frames claiming `0` collapse into one on generation and the second
         frame's code disappears without an error.

  LV009  error terminals the vendored lint cannot see .... round 9 + round 10
         `connection=` is a property of the TERMINAL, and both wrong values cost
         something invisible at the time:
           required  - the VI itself validates, compiles and runs, but every
                       caller that leaves that terminal unwired now breaks with
                       `Error 1003`. The fault is in the CALLER, from a flag in
                       the victim.
           optional  - identical behaviour at the call site, but the flag is
                       part of PlaceholderTools.Signature, so the same pane
                       hashes differently and yields a second stub clone.
         Upstream ALREADY reports part of this, and re-implementing covered
         ground is the mistake that retired LV002 (see its entry: two
         implementations drift). Its `conn-required-output` catches any
         Indicator marked required; its `conn-error-in-not-recommended` catches
         a Control named exactly `error in` - but ONLY when the terminal carries
         a conIdx, which is the case its author measured. Two gaps are left, and
         this rule is scoped to exactly those:
           a Control whose name starts with `error` and has NO conIdx
           an `error out` Indicator marked `optional`
         Anything with a conIdx is upstream's business. If upstream widens its
         rule, delete this one - do not let both count.
         Names are matched from the START so a legitimate `Last Error Count`
         control is not touched.

  LV010  <Constant> does not declare `description` ......... round 11 (live)
         LabVIEW refuses the WHOLE document at parse time with Error -2628:
         "attribute 'description' is not declared for element 'Constant'".
         Control and Indicator take it; Constant has a narrower whitelist. Round
         11 lost a round trip to this on a three-constant probe.

  LV011  a numeric terminal cannot have value="" ........... round 11 (live)
         The answer is "Unrecognized or unsupported attribute set in Indicator
         with UID n" - it names NEITHER attribute. Measured by A/B: removing
         `connection` changes nothing, setting value="0" fixes it. string and
         timestamp legitimately accept "", so the check is scoped by type;
         deleting `connection` first is the wrong instinct and costs an hour.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

UID_FLOOR = 4200          # LV002 - see the header, and docs/labview-crash-signatures.md
SENTINEL_UID = "0"        # reused freely, LabVIEW assigns its own id
COMMENT_RE = re.compile(r"<!--")
# LV009 - "error in", "error out", "error in (no error)", "Error Out 2". Anchored
# at the start so a legitimate control called "Last Error Count" is left alone.
ERROR_TERMINAL_RE = re.compile(r"^error\b", re.I)
# LV009's second half: upstream's `conn-required-output` already covers a required
# Indicator, so only the `optional` spelling of an output is left to report.
OUT_TERMINAL_RE = re.compile(r"^error out\b", re.I)
NUMERIC_RE = re.compile(r"^-?\d+$")


class Finding:
    __slots__ = ("severity", "code", "uid", "element", "path", "message")

    def __init__(self, severity, code, uid, element, path, message):
        self.severity = severity
        self.code = code
        self.uid = uid
        self.element = element
        self.path = path
        self.message = message

    def as_dict(self):
        return {
            "severity": self.severity,
            "check": self.code,
            "uid": self.uid,
            "element": self.element,
            "path": self.path,
            "message": self.message,
        }


class Node:
    __slots__ = ("el", "uid", "parent_uid", "path")

    def __init__(self, el, parent_uid, path):
        self.el = el
        self.uid = el.get("uid") or ""
        self.parent_uid = parent_uid
        self.path = path

    @property
    def tag(self):
        return self.el.tag

    def describe(self):
        name = self.el.get("_name") or self.el.get("_id") or self.el.tag
        return f"{self.el.tag} '{name}'" if name != self.el.tag else self.el.tag


def walk(root):
    """Every element that carries a uid, with its lexical parent's uid."""
    out = []

    def rec(el, parent_uid, path):
        for child in el:
            if not isinstance(child.tag, str):      # comments/PIs, dropped by ET anyway
                continue
            uid = child.get("uid") or ""
            child_path = f"{path}/{child.tag}[uid={uid}]" if uid else f"{path}/{child.tag}"
            declared = child.get("uid_parent")
            out.append(Node(child, declared if declared is not None else parent_uid, child_path))
            rec(child, uid or parent_uid, child_path)

    rec(root, "root", root.tag)
    return out


def nets_of(attr_value):
    """`terminal:net,terminal:net` -> [net]; escapes are left untouched."""
    nets = []
    for entry in (attr_value or "").split(","):
        if ":" not in entry:
            continue
        net = entry.split(":", 1)[1].strip()
        if net:
            nets.append(net)
    return nets


def producers(nodes):
    """net -> producing Node. First writer wins; duplicates are upstream's job."""
    prod = {}
    for n in nodes:
        el = n.el
        for net in nets_of(el.get("outputs")):
            prod.setdefault(net, n)
        if n.tag == "Structure":
            for attr in ("count", "maxout"):
                net = (el.get(attr) or "").strip()
                if net:
                    prod.setdefault(net, n)
        elif n.tag == "CaseFrame":
            net = (el.get("selectout") or "").strip()
            if net:
                prod.setdefault(net, n)
    return prod


def ancestry(nodes_by_uid, node):
    """uid list from the node up to root, following uid_parent."""
    chain, seen, cur = [], set(), node
    while cur is not None and cur.uid not in seen:
        seen.add(cur.uid)
        chain.append(cur.uid)
        cur = nodes_by_uid.get(cur.parent_uid)
    return chain


def check(path):
    findings = []
    raw = open(path, encoding="utf-8", errors="replace").read()

    # LV001 - checked on the TEXT, because a parser drops comments silently.
    for i, line in enumerate(raw.splitlines(), 1):
        if COMMENT_RE.search(line):
            findings.append(Finding(
                "error", "lv001-xml-comment", "-", "XML comment", f"line {i}",
                "AIXML must carry no XML comment: one before <VI> produces an EMPTY diagram with "
                "errorCode 0, one between children is Error 42. Use a <FreeLabel comment=\"...\"/> "
                "inside the VI, or the description attribute."))
            break

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        findings.append(Finding("error", "lv000-not-well-formed", "-", "document", "",
                                f"XML does not parse: {exc}"))
        return findings, 0

    if root.tag != "VI":
        findings.append(Finding(
            "info", "lv900-not-a-vi", "-", root.tag, "",
            f"root element is <{root.tag}>, not <VI> - this file is not an AIXML document "
            "(bundle dump or export?). Only lv000 applies."))
        return findings, 0

    nodes = walk(root)
    findings.extend(check_attributes(root, path))
    by_uid = {n.uid: n for n in nodes if n.uid}
    prod = producers(nodes)
    is_export = "exported" in os.path.basename(path).lower()   # kept for LV002's history

    for n in nodes:
        el = n.el

        # LV002 retired: upstream's uid-low reports the same uids. Nothing here.

        # LV003 - shift register seed must come from outside its loop.
        if n.tag == "ShiftReg":
            lefts = [c for c in el if c.tag == "Left"]
            rights = [c for c in el if c.tag == "Right"]
            if not lefts or not rights:                                  # LV007
                findings.append(Finding(
                    "error", "lv007-shiftreg-incomplete", n.uid, n.describe(), n.path,
                    "a ShiftReg needs both a <Left> (seed outside / value inside) and a <Right> "
                    "(new value inside / value outside); a half register does not convert."))
            for left in lefts:
                for net in nets_of(left.get("inputs")):
                    src = prod.get(net)
                    if src is None or src.uid == n.uid:
                        continue
                    if n.parent_uid in ancestry(by_uid, src):            # LV003
                        findings.append(Finding(
                            "error", "lv003-sr-seed-inside-loop", n.uid, n.describe(), n.path,
                            f"the seed net '{net}' is produced by {src.describe()} INSIDE the same "
                            "loop. The seed must be a root-level value carried across the border; "
                            "read inside, the composer reports a wire cycle that is not there. "
                            "(Rounds 3-4: two of five experiment arms failed exactly here.)"))

        # LV004 / LV008 - Case Structure frames.
        if n.tag == "Structure" and (el.get("_name") or "") == "Case Structure":
            frames = [c for c in el if c.tag == "CaseFrame"]
            if len(frames) <= 1 and (el.get("selectin") or "").strip():
                findings.append(Finding(
                    "error", "lv004-single-frame-case", n.uid, n.describe(), n.path,
                    "a Case Structure with one frame converts to state 0: the composer writes an "
                    "empty tunnel stub. Do not paper over it with a second selector - write the "
                    "straight-line logic instead. (Round 8, single-selector enum.)"))
            seen = {}
            for f in frames:
                sel = f.get("selector") or ""
                if sel in seen:                                          # LV008
                    findings.append(Finding(
                        "error", "lv008-duplicate-selector", f.get("uid") or n.uid,
                        f"CaseFrame '{sel}'", n.path,
                        f"two frames claim selector '{sel}'; on generation one of them wins and the "
                        "other frame's code disappears without an error."))
                seen[sel] = True

        # LV005 - While Loop stop.
        if n.tag == "Structure" and (el.get("_name") or "") == "While Loop":
            if not any(c.tag == "Condition" for c in el):
                findings.append(Finding(
                    "error", "lv005-while-without-condition", n.uid, n.describe(), n.path,
                    "the While Loop has no <Condition>: the diagram cannot stop it and LabVIEW "
                    "runs it forever. Add <Condition inputs=\"value:NET\" value=\"stop\"/>."))

        # LV006 - a Call target is a bare or library-qualified NAME.
        if n.tag == "Call":
            target = el.get("target") or ""
            if "/" in target or "\\" in target:
                findings.append(Finding(
                    "warning", "lv006-call-target-is-path", n.uid, n.describe(), n.path,
                    f"target '{target}' looks like a path. Generation resolves a target by NAME "
                    "against the installation or the loaded project - a path never resolves "
                    "(Error 53), unless the code is already loaded, and then only for conversion."))
            if not target:
                findings.append(Finding(
                    "error", "lv006-call-without-target", n.uid, n.describe(), n.path,
                    "a <Call> without target has nothing to resolve."))

    # LV009 - the connection flag on the error terminals upstream's rules miss.
    # Scope is deliberate: see the header. Anything carrying a conIdx belongs to
    # the vendored lint, and reporting it twice would bury the finding.
    for n in nodes:
        conn = n.el.get("connection")
        if not conn:
            continue
        name = n.el.get("_name") or n.el.get("name") or ""
        if not ERROR_TERMINAL_RE.match(name):
            continue
        if n.el.get("conIdx") is not None:
            continue
        if conn == "required":
            findings.append(Finding(
                "error", "lv009-error-terminal-required", n.uid, n.describe(), n.path,
                "an error terminal marked `required`: this VI still validates, compiles and "
                "runs, and every caller that leaves the terminal unwired now fails with "
                "Error 1003. Write connection=\"recommended\" for error in / error out."))
        elif conn == "optional" and OUT_TERMINAL_RE.match(name):
            findings.append(Finding(
                "warning", "lv009-error-out-optional", n.uid, n.describe(), n.path,
                "an `error out` terminal marked `optional`. Behaviour at the call site is the "
                "same as `recommended`, but the flag is part of the placeholder stub's "
                "signature, so the same pane hashes differently and produces a second clone. "
                "Normalise on connection=\"recommended\"."))

    return findings, len(nodes)


# LV010 / LV011 - the two attribute faults round 11 hit on a live LabVIEW, both of
# which are decidable from the document alone. Kept as a small separate pass so the
# element walk above stays readable.
NUMERIC_TYPES = {
    "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64",
    "double", "single", "ext", "cplx", "fixed-point",
}


def check_attributes(root, path):
    """LV010: attributes an element does not declare. LV011: empty numeric value."""
    findings = []

    def walk(el):
        yield el
        for child in el:
            yield from walk(child)

    for el in walk(root):
        uid = el.get("uid") or "-"
        name = el.get("_name") or el.get("name") or el.tag

        # LV010 - <Constant> has a fixed attribute whitelist that does NOT include
        # description. LabVIEW answers Error -2628 at PARSE time ("attribute
        # 'description' is not declared for element 'Constant'"), so the whole
        # document is refused, not just the attribute ignored.
        if el.tag == "Constant" and el.get("description") is not None:
            findings.append(Finding(
                "error", "lv010-constant-description", uid, f"Constant '{name}'", path,
                "`description` is not declared on <Constant> and ConvertAIXMLToVI refuses the "
                "whole document with Error -2628. Control and Indicator take it; Constant does "
                "not. Move the note to a FreeLabel or drop it."))

        # LV011 - a numeric terminal cannot carry value="". The answer is
        # "Unrecognized or unsupported attribute set in Indicator with UID n", which
        # names NEITHER attribute, so the natural next move is to delete `connection`
        # and lose an hour. string and timestamp legitimately take "".
        if el.tag in ("Constant", "Control", "Indicator"):
            typ = (el.get("type") or "").strip().lower()
            if typ in NUMERIC_TYPES and el.get("value") == "":
                findings.append(Finding(
                    "error", "lv011-numeric-empty-value", uid, f"{el.tag} '{name}'", path,
                    "a numeric terminal with value=\"\" - LabVIEW refuses it with "
                    "\"Unrecognized or unsupported attribute set\", which does not name the "
                    "attribute. Only string and timestamp accept an empty value; give numbers "
                    "a parseable literal such as 0."))

    return findings


SEV_ORDER = {"error": 0, "warning": 1, "info": 2}


def main(argv):
    ap = argparse.ArgumentParser(description="Offline check of this research's iron rules.")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true", help="machine readable")
    ap.add_argument("--min-severity", default="info", choices=["error", "warning", "info"])
    args = ap.parse_args(argv)

    results, worst = [], 2
    for path in args.files:
        findings, node_count = check(path)
        findings.sort(key=lambda f: (SEV_ORDER[f.severity], f.code))
        findings = [f for f in findings if SEV_ORDER[f.severity] <= SEV_ORDER[args.min_severity]]
        results.append({"file": path, "nodes": node_count,
                        "findings": [f.as_dict() for f in findings]})
        for f in findings:
            worst = min(worst, SEV_ORDER[f.severity])

    if args.json:
        total = sum(1 for r in results for f in r["findings"] if f["severity"] == "error")
        json.dump({"ok": total == 0, "errors": total, "files": results},
                  sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for r in results:
            if not r["findings"]:
                print(f"\n{r['file']}  [clean]  {r['nodes']} element(s)")
                continue
            errs = sum(1 for f in r["findings"] if f["severity"] == "error")
            warns = len(r["findings"]) - errs
            print(f"\n{r['file']}  [{errs} error(s), {warns} warning(s)]  {r['nodes']} element(s)")
            for f in r["findings"]:
                print(f"  {f['severity'].upper():7} {f['check']:<28} uid={f['uid']}  {f['element']}")
                print(f"          {f['message']}")
                print(f"          at {f['path']}")
        errs = sum(1 for r in results for f in r["findings"] if f["severity"] == "error")
        warns = sum(1 for r in results for f in r["findings"] if f["severity"] == "warning")
        print(f"\n{len(results)} file(s): {errs} error(s), {warns} warning(s), "
              f"{sum(1 for r in results for f in r['findings'] if f['severity'] == 'info')} info")
    return 1 if worst == 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

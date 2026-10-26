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

  LV012  a net crosses a structure boundary ................ round 12 (live)
         The composer refuses with `net 'N' crosses a diagram boundary
         without a tunnel`, and it names one net per attempt - so a document
         with four stray constants takes four round trips to repair. The rule
         was MISSING from this gate when round 12 first ran the round-7 event
         probe: LV001-LV011 were all clean (0 error / 5 warning) and the
         composer still refused the document twice. Both faults were the same
         one: a Constant at root consumed inside a CaseFrame, and a Constant
         inside the loop consumed inside an Event Structure's frames. A wire
         never crosses a structure border implicitly - each structure needs
         its outer Tunnel and each frame its own inner half, linked by _id.

  LV013  an Event Structure's Timeout cannot be wired ..... round 12 (live)
         There is no AIXML spelling for the `eventTimeOut` terminal. Writing
         <Tunnel _id="In1" inputs="value:500"/> at structure level buys an
         ORDINARY tunnel: measured round 12, the terminal stayed unwired
         (eventTimeOut dco referenced by no signal) and the run answered
         Timeouts=0 over 2.2 s with a 500 ms timeout - the loop waits forever.
         No error anywhere. The event frames THEMSELVES do survive (3
         EventSpecs, Timeout included) - it is the timeout value that is lost.

  LV014  a terminal with no conIdx is not on the pane ........ round 13 (live)
         The single reason the whole test layer was dead: `connection` decides
         required/recommended/optional, but only `conIdx` decides WHICH SLOT -
         and with no conIdx the composer writes conNum=-1 and leaves the
         skeleton's root objFlags 0x10000 ("NO TERMINAL ON THE PANE") alone.
         Then lvai_vi_terminals answers 0 in / 0 out, generate_test stops at
         `noTerminals`, and a Call to that VI composes and RUNS with nothing
         wired: measured, a caller whose only indicator came from its own
         constant answered 99 with no error while the callee did nothing.
         Sub-case worth knowing: SOME terminals paned is legal (a partial pane
         ran fine), and slots follow conIdx rather than document order.

  LV016  a class-qualified target is a NAME, not a path ....... round 15 (live)
         LV006 warns when a Call target contains `/` or `\`, reading it as a
         path that can never resolve. A class- or library-qualified name
         carries AIXML's escaped colon - `Sensor.lvclass\3ATag.vi` - and that
         backslash is escaping, not a separator. Measured round 15: the
         composer linked such a target against the loaded project (the report
         named `Call 'Sensor.lvclass:Tag.vi' <- ...`), the run executed it, and
         the swap's callTargets read it back. So the rule now strips every
         `\XX` hex escape before judging path-ness; a real Windows path
         (`C:\cls\X.vi`, `..\lib\X.vi`) still warns, because `\c`, `\l` are
         not escapes.
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
# LV012's severity depends on WHICH composer will read the document, and that is
# measured, not assumed: on `round4/batch-averager.aixml.xml` NI's converter
# (grpc) answers errorCode 0 and writes a 13,800-byte VI whose structure tunnels
# went 43 -> 154 (it creates every missing one), while pylabview's composer
# refuses the same file with "net '220.zero' crosses a diagram boundary without
# a tunnel". So: a warning on the grpc route, an error when the target is
# pylabview. `LVRULE_BACKEND=pylabview` (or --backend) sets it.
BOUNDARY_SEVERITY = "warning"
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


# --- LV012: which container a net's half actually lives in ------------------
# The boundary a net has to cross is not "the element's uid_parent". A Tunnel
# carries TWO halves: the outer one is drawn in the container of the structure
# that owns it, the inner one inside the frame. Reading uid_parent literally
# puts every tunnel on the wrong side and the rule then fires on correct files.

CONTAINER_TAGS = ("Structure", "CaseFrame")


def home_container(nodes_by_uid, node):
    """The container a half of this element lives in: 'root' or a uid."""
    if node.tag == "Tunnel":
        owner = nodes_by_uid.get(node.parent_uid)
        if owner is not None and owner.tag == "CaseFrame":
            return owner.uid                       # inner half: inside the frame
        if owner is not None and owner.tag == "Structure":
            return container_of(nodes_by_uid, owner)   # outer half: outside the structure
    return container_of(nodes_by_uid, node)


def container_of(nodes_by_uid, node):
    """Nearest enclosing Structure/CaseFrame uid, else 'root'."""
    seen, cur = set(), node
    while cur is not None and cur.uid not in seen:
        seen.add(cur.uid)
        parent = nodes_by_uid.get(cur.parent_uid)
        if parent is None:
            return "root"
        if parent.tag in CONTAINER_TAGS:
            return parent.uid
        cur = parent
    return "root"


def _tunnel_with(nodes_by_uid, container_uid, direction, net):
    """Child Tunnel of `container_uid` whose `direction` nets contain `net`."""
    container = nodes_by_uid.get(container_uid)
    if container is None:
        return None
    for child in container.el:
        if child.tag != "Tunnel":
            continue
        if net in nets_of(child.get(direction)):
            return child
    return None

def check_boundaries(nodes, nodes_by_uid):
    """LV012: every net that changes container must pass a tunnel."""
    findings = []

    prod, cons = {}, []
    for n in nodes:
        # A shift register's borders are not wires across a structure: Left is
        # the seed carried IN (it must come from outside - LV003) and Right is
        # the value carried OUT. Exempt, or every correct loop reports a fault.
        shift_border = n.tag in ("Left", "Right") and nodes_by_uid.get(n.parent_uid) is not None \
            and nodes_by_uid[n.parent_uid].tag == "ShiftReg"
        home = home_container(nodes_by_uid, n)
        for net in nets_of(n.el.get("outputs")):
            prod.setdefault(net, []).append(home)
        if shift_border:
            continue
        if n.tag == "CaseFrame":
            for net in nets_of(n.el.get("selectout")):
                prod.setdefault(net, []).append(n.uid)
        for net in nets_of(n.el.get("inputs")):
            cons.append((net, n, home))

    for net, node, home in cons:
        if net not in prod or home in prod[net]:
            continue
        # Walk outward, renaming the net at each tunnel it passes. Report the
        # FIRST missing hop: that is the one the composer names.
        cur, net_now, seen = home, net, set()
        crossed = False
        while cur not in prod[net] and cur not in seen:
            seen.add(cur)
            container = nodes_by_uid.get(cur)
            if container is None or cur == "root":
                break
            if container.tag == "CaseFrame":
                inner = _tunnel_with(nodes_by_uid, cur, "outputs", net_now)
                if inner is None:
                    findings.append(Finding(
                        BOUNDARY_SEVERITY, "lv012-net-crosses-boundary", node.uid, node.describe(), node.path,
                        f"net '{net_now}' is consumed in frame {cur} but produced outside it, and "
                        "this frame declares no <Tunnel _id=... outputs=\"value:...\"/> for it. "
                        "Each frame needs its OWN half of every tunnel, even when it does not use "
                        "the value: write outputs=\"value:\" there."))
                    crossed = None
                    break
                owner = nodes_by_uid.get(container.parent_uid)
                outer = None
                if owner is not None:
                    for child in owner.el:
                        if child.tag == "Tunnel" and child.get("_id") == inner.get("_id"):
                            outer = child
                            break
                if outer is None or not nets_of(outer.get("inputs")):
                    findings.append(Finding(
                        BOUNDARY_SEVERITY, "lv012-net-crosses-boundary", node.uid, node.describe(), node.path,
                        f"frame {cur} tunnels the net as _id='{inner.get('_id')}', but the "
                        f"enclosing {owner.tag if owner is not None else 'structure'} has no outer "
                        "half with that _id carrying inputs=\"value:...\". Both halves of a tunnel "
                        "must exist and agree on _id."))
                    crossed = None
                    break
                net_now = nets_of(outer.get("inputs"))[0]
                cur = container_of(nodes_by_uid, owner)
                crossed = True
            else:                                   # While / For: one element, both halves
                tun = _tunnel_with(nodes_by_uid, cur, "outputs", net_now)
                if tun is None:
                    findings.append(Finding(
                        BOUNDARY_SEVERITY, "lv012-net-crosses-boundary", node.uid, node.describe(), node.path,
                        f"net '{net_now}' is consumed inside {container.describe()} (uid {cur}) but "
                        "produced outside it, and the loop declares no tunnel for it. pylabview's "
                        "composer refuses the WHOLE document with \"net crosses a diagram boundary "
                        "without a tunnel\" and names one net per attempt; NI's converter (grpc) "
                        "quietly creates the missing tunnel instead (measured: 43 declared -> 154 in "
                        "the VI), so a document can pass on grpc and fail on pylabview. Move the "
                        "producer inside, or add <Tunnel _id=\"In1\" inputs=\"value:OUTER\" "
                        "outputs=\"value:INNER\"/>."))
                    crossed = None
                    break
                outer_nets = nets_of(tun.get("inputs"))
                if not outer_nets:
                    break
                net_now = outer_nets[0]
                cur = container_of(nodes_by_uid, container)
                crossed = True
        if crossed is None:
            continue
        if cur not in prod[net] and cur != "root":
            findings.append(Finding(
                BOUNDARY_SEVERITY, "lv012-net-crosses-boundary", node.uid, node.describe(), node.path,
                f"net '{net}' could not be traced back to a producer in an enclosing container; "
                "the wire has no path to a source."))
    return findings


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
    findings.extend(check_boundaries(nodes, by_uid))              # LV012
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

        # LV013 - an Event Structure's Timeout frame can never fire, because the
        # eventTimeOut terminal has no AIXML spelling. Measured round 12: the
        # tunnel written at structure level became an ORDINARY tunnel, the
        # terminal was left unwired, and the run answered Timeouts=0 over 2.2 s
        # with a 500 ms timeout wanted - no error anywhere.
        if n.tag == "Structure" and (el.get("_name") or "") == "Event Structure":
            timeouts = [f for f in el if f.tag == "CaseFrame"
                        and "timeout" in (f.get("selector") or "").lower()]
            if timeouts:
                findings.append(Finding(
                    "error", "lv013-event-timeout-unwireable", n.uid, n.describe(), n.path,
                    "this Event Structure has a ' Timeout ' frame, but AIXML has no way to wire "
                    "the structure's eventTimeOut terminal: a <Tunnel> here becomes an ordinary "
                    "tunnel and the terminal stays unwired, so the frame NEVER fires and the loop "
                    "waits forever (measured: Timeouts=0 over 2.2 s with 500 ms asked for). Wire "
                    "the timeout by hand in the IDE, or pace the loop with a Wait (ms) / Wait on "
                    "Notification and poll instead. The event frames themselves are fine."))

        # LV006 - a Call target is a bare or library-qualified NAME.
        if n.tag == "Call":
            target = el.get("target") or ""
            # LV016 (round 15): strip AIXML's \XX escapes before judging
            # path-ness - `Sensor.lvclass\3ATag.vi` is a qualified NAME whose
            # backslash escapes ':', and it resolves (measured: linked against
            # the loaded project, executed, and read back by the swap).
            bare = re.sub(r"\\[0-9A-Fa-f]{2}", "", target)
            if "/" in bare or "\\" in bare:
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

    # LV014 - a Control/Indicator with no conIdx is NOT on the connector pane.
    # Measured round 13, four ways. The composer writes conNum=-1 and leaves the
    # skeleton's root objFlags 0x10000 in place, whose own comment reads "NO
    # TERMINAL ON THE PANE". Everything downstream is silent: lvai_vi_terminals
    # answers "0 input(s), 0 output(s)", generate_test stops at `noTerminals`,
    # and a <Call> to such a VI COMPOSES AND RUNS with nothing wired - a caller
    # whose only output came from its own constant answered 99, no error, while
    # the callee did nothing. The A/B/C/D settled the mechanics: no conIdx -> no
    # pane; conIdx 0/1/2 -> pane; conIdx out of document order -> slots follow
    # conIdx (y at 0, x at 1, factor at 2), NOT document order; only x carrying
    # conIdx -> a PARTIAL pane, which is legal (execState 1, runs).
    # Severity is deliberate. All-off-the-pane is the normal shape of a top-level
    # UI VI, so it is info. SOME off and some on is what a forgotten conIdx looks
    # like, so that one is a warning - but legal (D proved it), hence not an error.
    paned = [n for n in nodes if n.tag in ("Control", "Indicator")]
    off = [n for n in paned if n.el.get("conIdx") is None]
    if off and len(off) == len(paned):
        findings.append(Finding(
            "info", "lv014-no-connector-pane", paned[0].uid, paned[0].describe(), paned[0].path,
            f"all {len(paned)} front-panel terminal(s) are off the connector pane, so this VI "
            "has no pane at all: it cannot be Called and a Caraya/NI test cannot drive it. "
            "Correct for a top-level UI VI, wrong for anything meant to be a subVI."))
    elif off:
        findings.append(Finding(
            "warning", "lv014-terminal-off-the-pane", off[0].uid, off[0].describe(), off[0].path,
            f"{len(off)} of {len(paned)} terminal(s) carry no conIdx and are off the pane: "
            + ", ".join(repr(n.el.get("_name") or "") for n in off)
            + ". A Call cannot name them, and an unwired Call runs with no error. "
            "Add conIdx to each you mean to expose."))

    # LV015 - a class-method SOURCE must carry conIdx, and this one is an ERROR.
    # Measured round 14, A/B on one class. `lvai_add_class_method` stamps
    # panePattern 4815 before the retype ("ConvertAIXMLToVI takes no pattern, so a
    # new VI otherwise carries the station default"), which sounds like it would
    # rescue a terminal that has no slot. It cannot, and it fails loudly:
    #
    #   Sensor/Scale By.vi  (conIdx 0/1/2) -> conpane ok, "pattern 4833 -> 4815,
    #                                        12 slots, no conIdx changed"
    #   Sensor/Reset.vi     (no conIdx)    -> conpane FAILED,
    #                                        "no <cons> array in the front-panel heap"
    #
    # The reason is mechanical and it also closes round 10's open question about
    # LV2026 FPHb: the <cons> array only EXISTS once at least one terminal has a
    # conIdx. A VI with none has no pane block for the editor to edit - so
    # "empty cons array" and "no pane" are the same fact, not a 2026 regression.
    # The signature below is the documented way a method is authored: path
    # stand-ins named `obj in` / `obj out`, retyped to the class afterwards.
    stand_ins = [n for n in paned
                 if (n.el.get("type") or "") in ("path", "string")
                 and (n.el.get("_name") or "") in ("obj in", "obj out")]
    if stand_ins and off:
        names = ", ".join(repr(n.el.get("_name") or "") for n in off)
        findings.append(Finding(
            "error", "lv015-method-stand-in-without-conidx", off[0].uid,
            off[0].describe(), off[0].path,
            f"this looks like a CLASS METHOD source (it carries an `obj in`/`obj out` "
            f"stand-in) and {len(off)} terminal(s) have no conIdx: {names}. "
            "lvai_add_class_method will pass convert and then DIE at its conpane step "
            "with `no <cons> array in the front-panel heap`, because that array only "
            "exists once one terminal has a slot. panePattern 4815 does not create it. "
            "Give every terminal a conIdx before handing the file to the tool."))

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
    ap.add_argument("--backend", default=os.environ.get("LVRULE_BACKEND", ""),
                    choices=["", "grpc", "pylabview"],
                    help="which composer the document is for: LV012 is a warning for grpc "
                         "(NI's converter creates the missing tunnels) and an error for pylabview "
                         "(its composer refuses the document)")
    args = ap.parse_args(argv)

    global BOUNDARY_SEVERITY
    if args.backend == "pylabview":
        BOUNDARY_SEVERITY = "error"

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

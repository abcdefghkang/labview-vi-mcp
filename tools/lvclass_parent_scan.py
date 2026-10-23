#!/usr/bin/env python3
"""lvclass_parent_scan.py - offline ground truth for "who is this class's parent?"

Why this exists
---------------
`lvai_describe_class` answers with an `inheritsFrom` field. Upstream measured that
field naming an INTERFACE as the parent for 46 of 437 classes on their station
(docs/cold-build-valverig.md). You cannot check that claim by reading either file:
the .lvclass does not contain the string `inheritsFrom` at all - the field is derived
by the tool. The ground truth is in the .lvclass itself, and it is two facts, not one:

  <Item Name="X.lvclass" Type="Parent" URL="..."/>   says WHOM this class names
  <Property Name="IsInterface" Type="Bool">TRUE</Property>  says what that thing IS

So a class that derives from an interface is, in the file, indistinguishable from
one that derives from a concrete class until you open the PARENT and read its
IsInterface. Any tool that reports the parent's identity without that second read is
reporting a name, not a relationship - which is exactly how an interface ends up
labelled as a base class.

MEASURED URL FORMS, and why resolution needs four attempts
----------------------------------------------------------
1. `/<vilib>/ChannelSupport/...`  angle-bracket ALIAS, expand it
                                  (vilib -> <LV>/vi.lib, resource -> <LV>/resource)
2. `../Lever/Lever.lvclass`        relative to the class's own folder - works
3. `../../Draw Message/...`       relative, but counted from the OWNING FOLDER, so a
                                  direct join lands one level too high. Measured on
                                  Event Messenger: Circle Message declares
                                  `../../Draw Message/Draw Message.lvclass` while the
                                  real hop is one level. Hence the one-up retry.
4. unique basename                last resort, and it is LABELLED as such in the row
                                  (`resolvedBy: basename`) so a report never implies
                                  more precision than it has.
Some URLs also end in `.lvclass.lvclass`; do not trust the tail.


No LabVIEW, no MCP, no network. Python 3 standard library only.

Usage
-----
  python lvclass_parent_scan.py "C:\\Program Files\\National Instruments\\LabVIEW 2026"
  python lvclass_parent_scan.py <root> --json out.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

PARENT_RE = re.compile(r'<Item\s[^>]*Type="Parent"[^>]*>', re.I)
URL_RE = re.compile(r'URL="([^"]*)"', re.I)


def read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def is_interface(path):
    """A class is an interface when its own file says IsInterface TRUE.

    The property is spelled `NI.LVClass.IsInterface`, not `IsInterface`. Reading the
    short form finds nothing and every class then looks concrete - measured on this
    station: 10 interfaces exist (Lever, Poundable, Pryable ...) and the short-name
    regex matched none of their parent lookups.
    """
    try:
        text = read_text(path)
    except OSError:
        return None
    m = re.search(
        r'<Property\s+Name="(?:NI\.LVClass\.)?IsInterface"[^>]*>([^<]*)</Property>',
        text, re.I)
    if not m:
        return False
    return m.group(1).strip().lower() in ("true", "1", "yes")


def parent_url(path):
    text = read_text(path)
    block = PARENT_RE.search(text)
    if not block:
        return None
    m = URL_RE.search(block.group(0))
    if not m:
        return None
    url = m.group(1)
    # XML attribute unescape (URLs carry &lt; &gt; &amp;)
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&amp;", "&")):
        url = url.replace(a, b)
    return url


def resolve(url, class_path, root, index=None):
    """Expand an .lvclass URL to (path, how) or (None, reason).

    Order matters: an exact answer always beats a fuzzy one, and the caller records
    WHICH rule fired so the report can say so.
    """
    if not url:
        return None, "no-url"
    if url.startswith("/"):
        # /<alias>/rest/of/path.lvclass   ->   alias is an angle-bracket token
        m = re.match(r"^/<([^>]+)>(.*)$", url)
        if m:
            alias, rest = m.group(1).lower(), m.group(2).lstrip("/").replace("/", os.sep)
            bases = {
                "vilib": os.path.join(root, "vi.lib"),
                "userlib": os.path.join(root, "user.lib"),
                "instrlib": os.path.join(root, "instr.lib"),
                "resource": os.path.join(root, "resource"),
                "labview": root,
            }
            base = bases.get(alias)
            if base is None:
                return None, f"unknown-alias:{alias}"
            target = os.path.normpath(os.path.join(base, rest))
            if os.path.isfile(target):
                return target, "alias"
            return target, "alias-missing"
        # a plain absolute URL we do not know how to anchor
        return None, "absolute-url"

    rel = url.replace("/", os.sep)
    here = os.path.dirname(class_path)

    direct = os.path.normpath(os.path.join(here, rel))
    if os.path.isfile(direct):
        return direct, "relative"

    # the owning-folder convention: one level higher than a direct join
    one_up = os.path.normpath(os.path.join(here, "..", rel))
    if os.path.isfile(one_up):
        return one_up, "relative-one-up"

    # last resort: a unique file name anywhere under the root
    if index:
        base = os.path.basename(rel)
        hits = index.get(base.lower()) or []
        if len(hits) == 1:
            return hits[0], "basename"
        if len(hits) > 1:
            return None, f"basename-ambiguous:{len(hits)}"
    return direct, "relative-missing"


def build_index(root):
    index = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".lvclass"):
                index.setdefault(name.lower(), []).append(os.path.join(dirpath, name))
    return index


def scan(root):
    classes, rows, stats = [], [], {
        "classes": 0, "with_parent": 0, "parent_is_interface": 0,
        "parent_unresolved": 0, "parent_file_missing": 0,
    }
    index = build_index(root)
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".lvclass"):
                classes.append(os.path.join(dirpath, name))

    for path in classes:
        stats["classes"] += 1
        url = parent_url(path)
        if not url:
            continue
        stats["with_parent"] += 1
        target, how = resolve(url, path, root, index)
        row = {"class": path, "url": url, "parentPath": target, "resolvedBy": how}
        if target is None or how in ("alias-missing", "relative-missing") and not target:
            stats["parent_unresolved"] += 1
            row["verdict"] = "unresolved"
        elif not os.path.isfile(target):
            stats["parent_file_missing"] += 1
            row["verdict"] = "parent-file-missing"
        else:
            ii = is_interface(target)
            row["parentIsInterface"] = ii
            if ii:
                stats["parent_is_interface"] += 1
                row["verdict"] = "parent-is-interface"
            else:
                row["verdict"] = "parent-is-class"
        rows.append(row)
    for r in rows:
        stats.setdefault("resolvedBy:" + str(r.get("resolvedBy")),
                         stats.get("resolvedBy:" + str(r.get("resolvedBy")), 0) + 1)
    return stats, rows


def main(argv):
    ap = argparse.ArgumentParser(description="offline parent/interface scan of .lvclass files")
    ap.add_argument("root", help="a LabVIEW installation or examples tree")
    ap.add_argument("--json", help="write the full per-class table here")
    ap.add_argument("--only-interface-parents", action="store_true",
                    help="print just the classes whose parent is an interface")
    args = ap.parse_args(argv)

    stats, rows = scan(args.root)
    print(f"root: {args.root}")
    for k in ("classes", "with_parent", "parent_is_interface",
              "parent_unresolved", "parent_file_missing"):
        print(f"  {k:<22} {stats[k]}")

    flagged = [r for r in rows if r["verdict"] == "parent-is-interface"]
    if flagged:
        print("\nclasses whose PARENT is an interface "
              "(a tool reporting the parent by name alone labels these as base classes):")
        for r in flagged:
            print("  " + os.path.relpath(r["class"], args.root))
            print(f"      -> {os.path.basename(r['parentPath'])}  [IsInterface TRUE]")

    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"root": args.root, "stats": stats, "rows": rows},
                      fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        print(f"\nwrote {args.json} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

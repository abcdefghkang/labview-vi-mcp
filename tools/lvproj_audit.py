#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check a .lvproj against the files on disk - the one gate in this folder that
reads a project file instead of AIXML.

WHY THIS EXISTS (round 14, measured)

`lvai_create_class` / `lvai_create_interface` write their `.lvclass` entry into
the .lvproj THEMSELVES, with LabVIEW not involved, and they say so: "LabVIEW
works in a throwaway project", "the entry is written into that one afterwards,
by this tool". That is the right design - and it means the entry exists on disk
while LabVIEW may still hold an IN-MEMORY copy of the same project that predates
it. The next time anything saves that stale copy - `lvai_close_active_project`,
the prologue of the next class tool, closing the IDE - the save writes the
in-memory item list over the file and THE ENTRY IS GONE. No error anywhere; the
file just quietly stops mentioning a class that is sitting right beside it.

What that costs: `lvai_create_accessors` answers

    classIndex: -1, classPathsSeen: ["...\\Can Scale.lvclass"]

for a project that lists three classes, because the active copy LabVIEW served
only ever knew about one. The hint it gives ("classIndex -1 with classPathsSeen
populated IS a path mismatch") then sends you looking at path spelling, which is
the wrong place.

Measured here on round 14's demo project: `Sensor.lvclass` and
`Temp Sensor.lvclass` were added, both read back as `action: "added"`, and both
were gone from the file after the next close. `No Override.lvclass` repeated it.

WHAT IT CHECKS

  error    a listed item whose file is not on disk (a URL that outlived its file)
  error    an item after Dependencies/Build (LabVIEW reorders them itself, and a
           hand-written file with a class below them has been seen not to load)
  warning  a .lvclass / .lvlib / .vi under the project's own tree that NO item
           lists - which is exactly what the clobbered entry looks like
  warning  a project with no My Computer item

Exit code is 1 when there is any error, 0 otherwise, so it can gate a script.

Usage
    python tools/lvproj_audit.py "research/artifacts/round14/Lvoop Demo.lvproj"
    python tools/lvproj_audit.py --summary research/artifacts
    python tools/lvproj_audit.py --json path/to/x.lvproj
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

# What a project can list under its own tree and what we look for on disk.
TREE_EXT = (".lvclass", ".lvlib", ".vi", ".ctl", ".vim", ".vit", ".llb")
SKIP_DIRS = {".git", "__pycache__", ".workbuddy", "out", "bundles", "Temp"}


def _resolve(url, base_file):
    """Resolve a LabVIEW item URL.

    A URL is relative to ITS OWNER FILE TREATED AS A DIRECTORY, not to the folder
    the owner sits in: from `round14/Lvoop Demo.lvproj`, `../lib/X.lvclass` means
    `round14/lib/X.lvclass`, and from `lib/Sensor.lvclass`, `../Sensor/Scale By.vi`
    means `lib/Sensor/Scale By.vi`. `../` is one level up from the file-as-folder,
    which is the file's own folder. Measured against what lvai_create_class
    actually writes and against what LabVIEW resolves; the naive
    `dirname(project)` base sends every path one level too high.
    """
    if not url:
        return None
    if url.startswith("/"):
        # /C/Users/... form: the leading / is a Windows path ROOT, and the drive
        # letter is the first component - so `/C/Users/x` is `C:\Users\x`, not the
        # relative `C/Users/x`.
        if len(url) > 2 and url[2:3] == "/":
            return os.path.normpath(url[1] + ":" + url[2:].replace("/", os.sep))
        return None
    return os.path.normpath(os.path.join(base_file, *url.split("/")))


def _walk_project_items(root):
    """Every <Item> with a URL, with the position of its parent chain."""
    out = []

    def rec(elem, chain):
        for child in elem:
            if child.tag != "Item":
                continue
            out.append((child, chain))
            rec(child, chain + [child.get("Name") or ""])

    rec(root, [])
    return out


def audit(project_path, ignore=()):
    findings = []

    def add(severity, code, message, name=None):
        findings.append({"severity": severity, "code": code, "message": message,
                         "name": name})

    project_path = os.path.abspath(project_path)
    project_dir = os.path.dirname(project_path)
    try:
        root = ET.parse(project_path).getroot()
    except Exception as exc:                                  # noqa: BLE001
        add("error", "proj-unreadable", "cannot parse the .lvproj: %s" % exc)
        return findings

    items = _walk_project_items(root)
    if not any(i.get("Type") == "My Computer" for i, _ in items):
        add("warning", "proj-no-my-computer",
            "no <Item Type=\"My Computer\"> - LabVIEW will not open this as a target")

    listed_files = set()
    seen_special = False
    for item, chain in items:
        typ = item.get("Type") or ""
        name = item.get("Name") or ""
        if typ in ("Dependencies", "Build"):
            seen_special = True
            continue
        if "Dependencies" in chain or "Build Specifications" in chain:
            continue                      # dependency + build items are not ours to police
        url = item.get("URL")
        if not url:
            continue
        path = _resolve(url, project_path)
        if path is None:
            add("warning", "proj-unresolvable-url",
                "URL %r is not relative and not an installation anchor" % url, name)
            continue
        listed_files.add(os.path.normcase(path))
        if not os.path.exists(path):
            add("error", "proj-item-missing",
                "listed as %r but %s is not on disk" % (name, path), name)
        if seen_special:
            add("error", "proj-item-after-build",
                "%r is listed after Dependencies/Build Specifications" % name, name)

    # A class or library lists its OWN members inside itself, not in the .lvproj.
    # Resolve those URLs too, or every method and accessor reads as "unlisted".
    for owner in sorted(listed_files):
        if not owner.lower().endswith((".lvclass", ".lvlib")):
            continue
        try:
            oroot = ET.parse(owner).getroot()
        except Exception:                                     # noqa: BLE001
            continue
        for inner in oroot.iter("Item"):
            p = _resolve(inner.get("URL"), owner)
            if p:
                listed_files.add(os.path.normcase(p))

    # Files on disk that nobody lists - the shape a clobbered entry leaves.
    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                       and not d.endswith(".UserState")]
        for fn in filenames:
            if not fn.lower().endswith(TREE_EXT):
                continue
            full = os.path.normcase(os.path.join(dirpath, fn))
            if full in listed_files:
                continue
            if any(os.path.normcase(os.path.abspath(p)) == full for p in ignore):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), project_dir)
            # An unlisted OWNER is the clobbered-entry shape and worth a warning. An
            # unlisted .vi is usually just a copy beside a project that references
            # another one by absolute URL (round 3 does exactly that), so it is
            # reported at info level and never fails the run.
            owner = fn.lower().endswith((".lvclass", ".lvlib"))
            add("warning" if owner else "info", "proj-file-unlisted",
                "%s exists but nothing lists it%s" %
                (rel, " - an unlisted owner is the clobbered-entry shape" if owner else ""),
                fn)

    return findings


def main(argv):
    ap = argparse.ArgumentParser(description="Check a .lvproj against the files on disk.")
    ap.add_argument("paths", nargs="+", help="a .lvproj or a directory to search")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--summary", action="store_true", help="counts only")
    ap.add_argument("--ignore", nargs="*", default=[], help="files to leave out")
    args = ap.parse_args(argv)

    files = []
    for p in args.paths:
        if os.path.isdir(p):
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                files += [os.path.join(dirpath, f) for f in filenames
                          if f.lower().endswith(".lvproj")]
        else:
            files.append(p)
    files = sorted(set(os.path.abspath(f) for f in files))
    if not files:
        print("no .lvproj found", file=sys.stderr)
        return 2

    report, errors = [], 0
    for f in files:
        findings = audit(f, args.ignore)
        errors += sum(1 for x in findings if x["severity"] == "error")
        report.append({"file": f, "findings": findings})

    if args.json:
        print(json.dumps({"projects": report}, indent=2, ensure_ascii=False))
        return 1 if errors else 0

    for entry in report:
        if args.summary:
            e = sum(1 for x in entry["findings"] if x["severity"] == "error")
            w = sum(1 for x in entry["findings"] if x["severity"] == "warning")
            print("%-70s [%dE/%dW]" % (os.path.relpath(entry["file"]), e, w))
            continue
        print(os.path.basename(entry["file"]))
        if not entry["findings"]:
            print("   clean")
        for x in entry["findings"]:
            print("   %-8s %-24s %s" % (x["severity"], x["code"], x["message"]))

    if args.summary:
        print("\n%d project(s), %d error(s)" % (len(report), errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

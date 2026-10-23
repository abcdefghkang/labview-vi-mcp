#!/usr/bin/env python3
"""cold_build_census.py - turn upstream's cold-build write-ups into a dataset.

Upstream ships 28 `docs/cold-build-*.md` files. Each one is the record of an
application built from nothing with these tools: what was made, what the final
state was, and every fault the run surfaced. Read one at a time they are
anecdotes; read as a corpus they answer the only question that matters for
"can an AI build a complex LabVIEW program":

    which faults actually recur, in which application shape, and what fixed them.

This script does no interpretation. It pulls the fields that are written in a
consistent shape (date, `Final state:` line, section titles, Error numbers,
tool names) and emits CSV + JSON so the report can quote counts instead of
impressions. Anything it cannot parse is reported as missing rather than
guessed - a blank cell is information.

Usage
    python tools/cold_build_census.py <docs-dir> [--out DIR] [--json]

<docs-dir> is a checkout of github.com/Zuehlke/labview-mcp (its docs/ folder).
Nothing here needs LabVIEW.
"""
import argparse
import collections
import csv
import glob
import json
import os
import re
import sys

# A build's date is stated in prose; these are the shapes that occur.
DATE_PATTERNS = [
    re.compile(r"Built from nothing on (\d{4}-\d{2}-\d{2})"),
    re.compile(r"built from nothing on (\d{4}-\d{2}-\d{2})"),
    re.compile(r"on (\d{4}-\d{2}-\d{2})[^.\n]*cold build"),
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
]

# The bolding is inconsistent across the corpus - the label is plain and the
# value is bold in most files, the reverse in a few - so accept both.
FINAL = re.compile(r"\*{0,2}Final state:\*{0,2}(.{0,400})", re.S)
SECTION = re.compile(r"\n## (\d+\.\s*[^\n]+)")
ERROR_NO = re.compile(r"Error (\d{3,4})")
TOOL = re.compile(r"\b(lvai_[a-z0-9_]+|pylabview|pylv_[a-z_]+|aixml_lint)\b")
# The headings that carry a fault, a fix or a wall - the analytical meat.
SIGNAL_HEADING = re.compile(
    r"fix|defect|fault|wall|fail|wrong|impossible|impossible|refut|silent|"
    r"trap|stale|trap|bug|regress|cost|budget|blocked|refus|leak|crash",
    re.I)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def first_date(text):
    for pat in DATE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    return ""


def final_state(text):
    m = FINAL.search(text)
    if not m:
        return "", {}
    raw = re.sub(r"\s+", " ", m.group(1)).strip()
    # The value itself is usually bolded, so `**` sits between the colon and
    # the first digit - splitting on it would return the empty prefix.
    raw = raw.replace("**", "").strip(" ,.;:")
    got = {}
    # `7 \`.lvclass\`` - inline code markers sit between the number and the noun
    # in about half the corpus, so strip them before matching.
    plain = raw.replace("`", "")
    for label, pat in (
        ("classes", r"(\d+)\s+(?:\.?lvclass|classes?)"),
        ("vis", r"(\d+)\s+VIs?\b"),
        ("tests", r"(\d+)\s+(?:LUnit |Caraya |VI Tester )?test(?:s|\b)"),
        ("failures", r"(\d+)\s+failures?"),
        ("errors", r"(\d+)\s+errors?"),
    ):
        m2 = re.search(pat, plain)
        if m2:
            got[label] = int(m2.group(1))
    return raw[:300], got


def census(docs_dir):
    files = sorted(glob.glob(os.path.join(docs_dir, "cold-build-*.md")))
    if not files:
        sys.exit(f"no cold-build-*.md under {docs_dir}")
    rows = []
    for path in files:
        text = read(path)
        name = os.path.basename(path)[:-3]
        title = text.split("\n")[0].lstrip("# ").strip()
        raw_final, nums = final_state(text)
        sections = [s.strip() for s in SECTION.findall(text)]
        signal = [s for s in sections if SIGNAL_HEADING.search(s)]
        errors = collections.Counter(ERROR_NO.findall(text))
        tools = collections.Counter(TOOL.findall(text))
        rows.append({
            "name": name,
            "title": title,
            "date": first_date(text),
            "lines": text.count("\n") + 1,
            "sections": len(sections),
            "signal_sections": len(signal),
            "signal_titles": " | ".join(signal)[:600],
            "final_state": raw_final,
            **{k: nums.get(k, "") for k in ("classes", "vis", "tests", "failures")},
            "error_numbers": " ".join(f"{k}x{v}" for k, v in errors.most_common()),
            "tools_used": len(tools),
            "tools": " ".join(sorted(tools)),
            "has_negative_control": "negative control" in text.lower(),
            "mentions_lint": "aixml_lint" in text or "lint" in text.lower(),
        })
    return rows


def summarise(rows):
    """Corpus-level counts. These are the numbers the report cites."""
    err = collections.Counter()
    err_files = collections.defaultdict(set)
    tool = collections.Counter()
    tool_files = collections.defaultdict(set)
    for r in rows:
        for chunk in r["error_numbers"].split():
            num, _, n = chunk.partition("x")
            err[num] += int(n or 1)
            err_files[num].add(r["name"])
        for t in r["tools"].split():
            tool[t] += 1
            tool_files[t].add(r["name"])
    return {
        "builds": len(rows),
        "dated": sum(1 for r in rows if r["date"]),
        "with_final_state": sum(1 for r in rows if r["classes"] != ""),
        "zero_failure": sum(1 for r in rows if r["failures"] == 0),
        "with_negative_control": sum(1 for r in rows if r["has_negative_control"]),
        "with_lint": sum(1 for r in rows if r["mentions_lint"]),
        "signal_sections": sum(r["signal_sections"] for r in rows),
        "sections": sum(r["sections"] for r in rows),
        "total_lines": sum(r["lines"] for r in rows),
        "classes": sum(r["classes"] for r in rows if isinstance(r["classes"], int)),
        "vis": sum(r["vis"] for r in rows if isinstance(r["vis"], int)),
        "tests": sum(r["tests"] for r in rows if isinstance(r["tests"], int)),
        "errors_by_number": dict(err.most_common(20)),
        "error_files": {k: sorted(v) for k, v in
                        sorted(err_files.items(), key=lambda kv: -len(kv[1]))[:20]},
        "tools_by_builds": dict(tool.most_common(30)),
        "tool_files": {k: len(v) for k, v in tool_files.items()},
    }


def write_csv(rows, path):
    cols = ["name", "date", "lines", "sections", "signal_sections", "classes", "vis",
            "tests", "failures", "tools_used", "has_negative_control", "title",
            "final_state", "error_numbers", "tools", "signal_titles"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("docs", help="upstream checkout's docs/ directory")
    ap.add_argument("--out", default="", help="write cold-build-census.csv/.json here")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = ap.parse_args(argv)

    rows = census(args.docs)
    stats = summarise(rows)

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        write_csv(rows, os.path.join(args.out, "cold-build-census.csv"))
        with open(os.path.join(args.out, "cold-build-census.json"), "w",
                  encoding="utf-8", newline="\n") as fh:
            json.dump({"summary": stats, "builds": rows}, fh,
                      ensure_ascii=False, indent=1)
            fh.write("\n")

    if args.json:
        print(json.dumps({"summary": stats, "builds": rows},
                         ensure_ascii=False, indent=1))
        return 0

    print(f"{stats['builds']} cold builds, {stats['total_lines']} lines, "
          f"{stats['sections']} sections ({stats['signal_sections']} about a "
          f"fault/fix/wall)")
    print(f"  dated {stats['dated']} · final-state {stats['with_final_state']} · "
          f"0-failure {stats['zero_failure']} · negative control "
          f"{stats['with_negative_control']} · lint {stats['with_lint']}")
    if stats["classes"]:
        print(f"  authored: {stats['classes']} .lvclass, {stats['vis']} VIs, "
              f"{stats['tests']} tests across the builds that state them")
    print("\nerror numbers, by mentions:")
    for num, n in stats["errors_by_number"].items():
        print(f"  Error {num:<5} {n:>3} mentions in {len(stats['error_files'][num])} build(s)")
    print("\ntools, by number of builds that used them:")
    for t, n in stats["tools_by_builds"].items():
        print(f"  {t:<34} {n:>2} build(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

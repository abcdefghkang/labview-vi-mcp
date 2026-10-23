"""Generate the round-13 connector-pane A/B/C/D probes.

All four are the same VI - y = x * factor - and differ only in how the three
terminals are declared against the connector pane:

    A  no conIdx at all              (what every AIXML this project wrote so far looks like)
    B  conIdx 0 / 1 / 2 in document order
    C  conIdx out of document order  (proves the slot is taken from conIdx, not from order)
    D  only x carries conIdx 0       (is a PARTIAL pane legal, or all-or-nothing?)
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))

HEAD = '''<VI _name="{name}" description="Round-13 connector-pane probe: y = x * factor. Identical in all four variants; only conIdx differs, so any difference in the connector pane is caused by conIdx and nothing else.">
'''

BODY = {
    "A": [
        ('<Control _name="x" connection="recommended" outputs="value:4200.value" type="double" uid="4200" uid_parent="root" value="1"/>', None),
        ('<Control _name="factor" connection="recommended" outputs="value:4201.value" type="double" uid="4201" uid_parent="root" value="2"/>', None),
        ('<Indicator _name="y" connection="recommended" inputs="value:4210.out" type="double" uid="4210" uid_parent="root" value="0"/>', None),
    ],
    "B": [
        ('<Control _name="x" connection="recommended" conIdx="0" outputs="value:4200.value" type="double" uid="4200" uid_parent="root" value="1"/>', 0),
        ('<Control _name="factor" connection="recommended" conIdx="1" outputs="value:4201.value" type="double" uid="4201" uid_parent="root" value="2"/>', 1),
        ('<Indicator _name="y" connection="recommended" conIdx="2" inputs="value:4210.out" type="double" uid="4210" uid_parent="root" value="0"/>', 2),
    ],
    # C: y takes slot 0, x slot 1, factor slot 2 - deliberately reversed relative to the document
    "C": [
        ('<Control _name="x" connection="recommended" conIdx="1" outputs="value:4200.value" type="double" uid="4200" uid_parent="root" value="1"/>', 1),
        ('<Control _name="factor" connection="recommended" conIdx="2" outputs="value:4201.value" type="double" uid="4201" uid_parent="root" value="2"/>', 2),
        ('<Indicator _name="y" connection="recommended" conIdx="0" inputs="value:4210.out" type="double" uid="4210" uid_parent="root" value="0"/>', 0),
    ],
    # D: only x is on the pane
    "D": [
        ('<Control _name="x" connection="recommended" conIdx="0" outputs="value:4200.value" type="double" uid="4200" uid_parent="root" value="1"/>', 0),
        ('<Control _name="factor" connection="recommended" outputs="value:4201.value" type="double" uid="4201" uid_parent="root" value="2"/>', None),
        ('<Indicator _name="y" connection="recommended" inputs="value:4210.out" type="double" uid="4210" uid_parent="root" value="0"/>', None),
    ],
}

TAIL = ('  <Node _name="Multiply" inputs="x:4200.value,y:4201.value" '
        'outputs="x*y:4210.out" uid="4211" uid_parent="root"/>\n</VI>\n')


def write(tag):
    name = "Conpane Probe %s.vi" % tag
    lines = [HEAD.format(name=name)]
    for el, _ in BODY[tag]:
        lines.append("  " + el + "\n")
    lines.append(TAIL)
    path = os.path.join(HERE, "conidx-probe-%s.aixml.xml" % tag.lower())
    io.open(path, "w", encoding="utf-8", newline="\n").write("".join(lines))
    print(path)


for t in "ABCD":
    write(t)

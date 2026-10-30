# -*- coding: utf-8 -*-
"""Minimal MCP stdio driver for LabVIEWMCP.exe — reproduce rounds without an MCP-capable IDE.

The labview-mcp server speaks MCP as newline-delimited JSON-RPC over stdin/stdout.
This script spawns the server, performs the initialize handshake, then either lists
the tool surface or calls one tool, printing the raw result JSON to stdout.

Why it exists: every measured round in research/ assumed the agent had the lvai_*
tools mounted by its IDE. On a bare shell (or a CI box) that is not true, and
"can I even drive the server at all" is the first environment trap the board warns
about. This script is the 60-line answer: the same tools, one JSON-RPC layer down.

Usage (bundled Python 3.12, no third-party deps):

  python mcp_call.py --server "C:\\path\\LabVIEWMCP.exe" list [--out tools.json]
  python mcp_call.py --server "C:\\path\\LabVIEWMCP.exe" call lvai_status
  python mcp_call.py --server ... call lvai_convert_aixml_to_vi ^
      --args "{\"aiXmlFilePath\":\"C:\\\\LV_AUTOTEST\\\\x.aixml.xml\", ...}" --timeout 300
  python mcp_call.py --server ... batch --plan plan.json --out transcript.json

Batch mode (round 21): the plan file is a JSON array of steps, or an object
{"label": ..., "steps": [...]}. Each step is {"name": <tool>, "args": {...},
"timeout": seconds (optional, --timeout wins as default)}. Steps run IN ORDER over
one server session - one handshake, N calls - which is what makes a whole round
reproducible from one JSON file: "a round = a plan + one run". Every step is
recorded verbatim into the merged transcript; a failing step does NOT stop the run
(the real failure shape of the follow-ups is evidence too).

Exit codes: 0 ok, 2 transport/handshake error, 3 tool returned isError, 4 timeout.
Batch: exit 3 if ANY step failed (exception or isError).
"""
import argparse
import json
import subprocess
import sys
import threading
import time

def LOG(fmt, *args):
    print("[mcp_call] " + (fmt % args), file=sys.stderr, flush=True)


class McpClient:
    def __init__(self, exe_path):
        self.exe_path = exe_path
        self.proc = None
        self.pending = {}
        self.pending_lock = threading.Lock()
        self.next_id = 1
        self.notifications = []

    def _reader(self):
        """One line = one JSON-RPC message. Notifications carry no id."""
        for raw in self.proc.stdout:
            line = raw.strip()
            if not line:
                continue
            try:
                msg = json.loads(line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError as exc:
                LOG("[non-json] %s (%s)", line[:200], exc)
                continue
            if "id" in msg and msg["id"] is not None:
                with self.pending_lock:
                    ev = self.pending.pop(msg["id"], None)
                if ev is not None:
                    ev["msg"] = msg
                    ev["event"].set()
                else:
                    LOG("[stray response id=%s]", msg["id"])
            else:
                self.notifications.append(msg)
                LOG("[notify] %s %s",
                          msg.get("method", "?"),
                          json.dumps(msg.get("params", {}), ensure_ascii=False)[:300])
        LOG("[reader exited, exitcode=%s]", self.proc.poll())

    def start(self, timeout=30):
        self.proc = subprocess.Popen(
            [self.exe_path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.reader_thread = threading.Thread(target=self._reader, daemon=True)
        self.reader_thread.start()
        self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "labview-vi-mcp-driver", "version": "1.0"},
        }, timeout=timeout)
        self._notify("notifications/initialized", {})
        return self

    def _notify(self, method, params):
        self.proc.stdin.write((json.dumps(
            {"jsonrpc": "2.0", "method": method, "params": params}) + "\n").encode())
        self.proc.stdin.flush()

    def _request(self, method, params, timeout=120):
        rid = self.next_id
        self.next_id += 1
        ev = {"event": threading.Event(), "msg": None}
        with self.pending_lock:
            self.pending[rid] = ev
        self.proc.stdin.write((json.dumps(
            {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n").encode())
        self.proc.stdin.flush()
        if not ev["event"].wait(timeout):
            with self.pending_lock:
                self.pending.pop(rid, None)
            raise TimeoutError("%s timed out after %ss (server alive: %s)" % (
                method, timeout, self.proc.poll() is None))
        msg = ev["msg"]
        if "error" in msg:
            raise RuntimeError("JSON-RPC error: %s" % json.dumps(msg["error"], ensure_ascii=False))
        return msg["result"]

    def list_tools(self):
        return self._request("tools/list", {})

    def call(self, name, arguments, timeout=120):
        return self._request("tools/call",
                             {"name": name, "arguments": arguments}, timeout=timeout)

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def run_batch(client, plan, default_timeout):
    """Execute plan steps in order; never stop on a failing step (record instead)."""
    steps = plan["steps"] if isinstance(plan, dict) else plan
    if isinstance(steps, dict):
        steps = [steps]
    transcript = []
    for i, step in enumerate(steps, 1):
        name = step["name"]
        arguments = step.get("args", {})
        timeout = step.get("timeout", default_timeout)
        entry = {"step": i, "name": name, "args": arguments,
                 "ok": False, "result": None, "error": None}
        t0 = time.perf_counter()
        try:
            result = client.call(name, arguments, timeout=timeout)
            entry["result"] = result
            entry["isError"] = bool(isinstance(result, dict) and result.get("isError"))
            entry["ok"] = not entry["isError"]
        except Exception as exc:  # TimeoutError / RuntimeError / OSError - record, continue
            entry["error"] = "%s: %s" % (type(exc).__name__, exc)
        entry["elapsedMs"] = int((time.perf_counter() - t0) * 1000)
        transcript.append(entry)
        LOG("[step %d/%d] %s -> %s (%d ms)", i, len(steps), name,
            "ok" if entry["ok"] else "FAILED", entry["elapsedMs"])
    return transcript


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--server", required=True, help="path to LabVIEWMCP.exe")
    ap.add_argument("mode", choices=["list", "call", "batch"])
    ap.add_argument("tool", nargs="?", help="tool name (mode=call)")
    ap.add_argument("--args", default="{}", help="tool arguments as JSON")
    ap.add_argument("--args-file", help="read tool arguments JSON from this file (wins over --args)")
    ap.add_argument("--plan", help="batch mode: JSON plan file (array of steps or {label, steps})")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--out", help="write raw result JSON here instead of stdout")
    args = ap.parse_args()

    client = McpClient(args.server)
    try:
        client.start()
        if args.mode == "list":
            result = client.list_tools()
            text = json.dumps(result, ensure_ascii=False, indent=1)
        elif args.mode == "batch":
            if not args.plan:
                ap.error("mode=batch requires --plan")
            with open(args.plan, "r", encoding="utf-8") as fh:
                plan = json.load(fh)
            steps = run_batch(client, plan, args.timeout)
            failed = [e for e in steps if not e["ok"]]
            result = {
                "label": plan.get("label") if isinstance(plan, dict) else None,
                "planFile": args.plan,
                "server": args.server,
                "stepsRun": len(steps),
                "failed": len(failed),
                "allOk": not failed,
                "steps": steps,
            }
            text = json.dumps(result, ensure_ascii=False, indent=1)
            LOG("[batch done] %d steps, %d failed", len(steps), len(failed))
            if args.out:
                with open(args.out, "w", encoding="utf-8") as fh:
                    fh.write(text)
                LOG("[written] %s (%d bytes)", args.out, len(text))
            else:
                print(text)
            return 3 if failed else 0
        else:
            if not args.tool:
                ap.error("mode=call requires a tool name")
            try:
                if args.args_file:
                    with open(args.args_file, "r", encoding="utf-8") as fh:
                        arguments = json.load(fh)
                else:
                    arguments = json.loads(args.args)
            except json.JSONDecodeError as exc:
                ap.error("tool arguments are not valid JSON: %s" % exc)
            result = client.call(args.tool, arguments, timeout=args.timeout)
            text = json.dumps(result, ensure_ascii=False, indent=1)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
            LOG("[written] %s (%d bytes)", args.out, len(text))
        else:
            print(text)
        is_error = isinstance(result, dict) and result.get("isError")
        return 3 if is_error else 0
    except TimeoutError as exc:
        LOG("[timeout] %s", exc)
        return 4
    except (RuntimeError, OSError) as exc:
        LOG("[error] %s", exc)
        return 2
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())


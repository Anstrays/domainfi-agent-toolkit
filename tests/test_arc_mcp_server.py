from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class ArcMcpServerTests(unittest.TestCase):
    def _call(self, request: dict) -> dict:
        proc = subprocess.run(
            [sys.executable, "-m", "domainfi_toolkit.arc_mcp"],
            input=json.dumps(request) + "\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=REPO_ROOT,
            env={"PYTHONPATH": str(REPO_ROOT / "src")},
            timeout=5,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, proc.stdout)
        return json.loads(lines[0])

    def test_mcp_initialize_lists_arc_tools(self) -> None:
        response = self._call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"]["serverInfo"]["name"], "domainfi-arc-mcp")
        self.assertIn("tools", response["result"]["capabilities"])

        tools = self._call({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = {tool["name"] for tool in tools["result"]["tools"]}
        self.assertIn("domainfi_arc_payment_intent", names)
        self.assertIn("domainfi_arc_payment_verify", names)
        self.assertIn("domainfi_arc_paid_scan", names)

    def test_mcp_call_tool_returns_content_and_structured_result(self) -> None:
        response = self._call(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "domainfi_arc_payment_verify",
                    "arguments": {
                        "payment": "x402-test:domainfi.discovery.scan:25000",
                        "resource": "domainfi.discovery.scan",
                        "amount_microusd": 25000,
                    },
                },
            }
        )
        self.assertTrue(response["result"]["structuredContent"]["paid"])
        self.assertEqual(response["result"]["structuredContent"]["status"], "accepted")
        self.assertEqual(response["result"]["content"][0]["type"], "text")

    def test_mcp_rejects_unknown_tool_without_crashing(self) -> None:
        response = self._call(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "nope", "arguments": {}},
            }
        )
        self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("unknown tool", response["error"]["message"])


if __name__ == "__main__":
    unittest.main()

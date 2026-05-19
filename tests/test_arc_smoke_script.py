from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class ArcPaidAgentSmokeScriptTests(unittest.TestCase):
    def test_smoke_script_exercises_unpaid_and_paid_http_flow(self) -> None:
        proc = subprocess.run(
            [sys.executable, "scripts/smoke_arc_paid_agent.py"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=REPO_ROOT,
            timeout=15,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("unpaid_status=402", proc.stdout)
        self.assertIn("paid_status=200", proc.stdout)
        self.assertIn("payment_receipt=accepted", proc.stdout)
        self.assertIn("opportunities=", proc.stdout)


if __name__ == "__main__":
    unittest.main()

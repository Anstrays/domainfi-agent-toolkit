from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO_ROOT / "examples" / "arc-x402-paid-agent" / ".env.example"
DEPLOY_DOC = REPO_ROOT / "docs" / "ARC_PRODUCTION_DEPLOYMENT.md"
LIVE_SMOKE = REPO_ROOT / "scripts" / "live_arc_gateway_smoke.py"


class ArcDeploymentAssetsTests(unittest.TestCase):
    def test_arc_env_example_is_scoped_to_arc_gateway(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("DOMAINFI_PAYMENT_MODE" + "=gateway", text)
        self.assertIn("CIRCLE_GATEWAY_URL" + "=", text)
        self.assertIn("CIRCLE_GATEWAY_" + "API_KEY" + "=", text)
        self.assertIn("ARC_PAID_AGENT_URL" + "=", text)
        self.assertIn("ARC_LIVE_X_PAYMENT" + "=", text)
        self.assertNotIn("DOMA_API", text)
        self.assertNotIn("doma-http", text.lower())

    def test_arc_deploy_doc_has_checklist_and_smoke_path(self) -> None:
        text = DEPLOY_DOC.read_text(encoding="utf-8")
        self.assertIn("# Arc Production Deployment", text)
        self.assertIn("## Production deployment checklist", text)
        self.assertIn("## Live smoke test", text)
        self.assertIn("scripts/live_arc_gateway_smoke.py", text)
        self.assertIn("CIRCLE_GATEWAY_URL", text)
        self.assertIn("DOMAINFI_PAYMENT_MODE" + "=gateway", text)
        self.assertNotIn("DOMA_API", text)
        self.assertNotIn("doma-http", text.lower())

    def test_live_smoke_requires_agent_url(self) -> None:
        env = os.environ.copy()
        env.pop("ARC_PAID_AGENT_URL", None)
        env.pop("ARC_LIVE_X_PAYMENT", None)
        result = subprocess.run(
            [sys.executable, str(LIVE_SMOKE)],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("ARC_PAID_AGENT_URL", result.stderr)


if __name__ == "__main__":
    unittest.main()

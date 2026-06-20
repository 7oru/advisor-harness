from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.harness.defaults import init_workspace
from packages.harness.runner import run_task
from packages.harness.ui import build_dashboard_payload, render_dashboard


class UiTests(TestCase):
    def test_dashboard_payload_uses_persisted_runs(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_workspace(root)
            result = run_task(
                root=root,
                task="fake smoke task",
                executor_backend="fake",
                advisor_backend="fake",
                timeout_seconds=10,
            )

            payload = build_dashboard_payload(root)

            self.assertEqual(payload["selected_run_id"], result.run_id)
            self.assertEqual(payload["runs"][0]["run_id"], result.run_id)
            self.assertEqual(payload["runs"][0]["status"], "completed")
            self.assertEqual(payload["payloads"][result.run_id]["run"]["advisor_consult_count"], 1)
            self.assertEqual(len(payload["payloads"][result.run_id]["events"]), 7)

    def test_render_dashboard_writes_local_html(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_workspace(root)
            result = run_task(
                root=root,
                task="fake smoke task",
                executor_backend="fake",
                advisor_backend="fake",
                timeout_seconds=10,
            )

            path = render_dashboard(root, run_id=result.run_id)

            self.assertEqual(path, root / "runs" / "ui" / "index.html")
            html = path.read_text(encoding="utf-8")
            self.assertIn("<title>Advisor Runs</title>", html)
            self.assertIn(result.run_id, html)
            self.assertIn("status-filter", html)
            self.assertIn("Prompts And Raw Output", html)

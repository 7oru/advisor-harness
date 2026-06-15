from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.harness.defaults import init_workspace
from packages.harness.security_questionnaire import run_security_questionnaire


class SecurityQuestionnaireTests(TestCase):
    def test_fake_security_workflow_writes_expected_artifacts(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_workspace(root)
            questionnaire = root / "questionnaire.csv"
            knowledge = root / "knowledge"
            knowledge.mkdir()
            questionnaire.write_text("id,question\nQ1,Do you support SSO?\n", encoding="utf-8")
            (knowledge / "security.md").write_text("SSO is supported via SAML.\n", encoding="utf-8")

            result = run_security_questionnaire(
                root=root,
                questionnaire=questionnaire,
                knowledge=knowledge,
                executor_backend="fake",
                advisor_backend="fake",
                timeout_seconds=10,
            )

            for filename in (
                "answers_draft.md",
                "evidence_links.md",
                "risk_flags.md",
                "open_questions.md",
            ):
                self.assertTrue((result.run_dir / filename).exists())

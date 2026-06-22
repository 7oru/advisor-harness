import json
from unittest import TestCase

from packages.harness.improvements import (
    IMPROVEMENT_PROPOSAL_SCHEMA_VERSION,
    extract_improvement_proposals,
    improvement_proposals_markdown,
)


def _proposal(target):
    return {
        "id": "{}_1".format(target),
        "target": target,
        "title": "Improve {}".format(target),
        "rationale": "The post-run review found a reusable improvement.",
        "evidence": "The run artifact shows the issue.",
        "proposed_change": "Adjust the {} guidance text.".format(target),
        "validation_plan": "Run the fake regression suite.",
        "requires_human_approval": True,
        "status": "proposed",
    }


class ImprovementProposalTests(TestCase):
    def test_extracts_valid_human_approval_only_packet(self):
        packet = {
            "schema_version": IMPROVEMENT_PROPOSAL_SCHEMA_VERSION,
            "summary": "Three advisory improvements.",
            "proposals": [
                _proposal("memory_schema"),
                _proposal("executor_prompt"),
                _proposal("advisor_prompt"),
            ],
        }
        text = "\n".join(
            [
                "Review text.",
                "<IMPROVEMENT_PROPOSALS>",
                json.dumps(packet, indent=2, sort_keys=True),
                "</IMPROVEMENT_PROPOSALS>",
            ]
        )

        result = extract_improvement_proposals(text, run_id="run_1")

        self.assertTrue(result["validation"]["valid"])
        self.assertEqual(result["source_run_id"], "run_1")
        self.assertEqual([item["target"] for item in result["proposals"]], list(("memory_schema", "executor_prompt", "advisor_prompt")))
        self.assertTrue(all(item["requires_human_approval"] for item in result["proposals"]))

    def test_rejects_missing_target_and_auto_apply_proposal(self):
        packet = {
            "schema_version": IMPROVEMENT_PROPOSAL_SCHEMA_VERSION,
            "proposals": [
                dict(_proposal("memory_schema"), requires_human_approval=False),
                _proposal("executor_prompt"),
            ],
        }
        text = "<IMPROVEMENT_PROPOSALS>{}</IMPROVEMENT_PROPOSALS>".format(json.dumps(packet))

        result = extract_improvement_proposals(text, run_id="run_1")

        self.assertFalse(result["validation"]["valid"])
        self.assertIn("proposals[0].requires_human_approval must be true", result["validation"]["errors"])
        self.assertIn("missing proposal target: advisor_prompt", result["validation"]["errors"])

    def test_missing_block_returns_invalid_empty_packet(self):
        result = extract_improvement_proposals("No structured proposals.", run_id="run_1")

        self.assertFalse(result["validation"]["valid"])
        self.assertEqual(result["proposals"], [])
        self.assertIn("missing <IMPROVEMENT_PROPOSALS> block", result["validation"]["errors"])

    def test_markdown_includes_validation_state(self):
        result = extract_improvement_proposals("No structured proposals.", run_id="run_1")

        markdown = improvement_proposals_markdown(result)

        self.assertIn("# Improvement Proposals", markdown)
        self.assertIn("missing <IMPROVEMENT_PROPOSALS> block", markdown)


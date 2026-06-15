from unittest import TestCase

from packages.harness.parser import parse_json_blocks


class ParserTests(TestCase):
    def test_parse_json_block(self):
        text = '<ADVISOR_CONSULT>{"question":"x","context":"y"}</ADVISOR_CONSULT>'
        self.assertEqual(parse_json_blocks(text, "ADVISOR_CONSULT")[0]["question"], "x")
